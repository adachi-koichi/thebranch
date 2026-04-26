"""
Cross-Department Collaboration API Tests (Task #2486)

cross_dept_tasks テーブルに対する 4 つの API エンドポイント、権限チェック、
WebSocket 通知（notification_logs 経由）の統合テスト。

エンドポイント:
- POST /api/departments/{dept_id}/cross-dept-tasks
- GET  /api/departments/{dept_id}/incoming-requests
- PUT  /api/cross-dept-tasks/{task_id}/accept
- PUT  /api/cross-dept-tasks/{task_id}/reject

検証観点:
- 正常系（201/200）
- 認可: 非メンバーは 403
- 存在しない部署/タスク: 404
- 状態遷移: pending → accepted/rejected のみ。再遷移は 409
- バリデーション: task_name 空 / 同一部署依頼 → 400/422
- 通知: accept/reject 時に notification_logs に記録
"""

import pytest
import sqlite3
import uuid
from pathlib import Path
from httpx import AsyncClient, ASGITransport


# ─── テストフィクスチャ ─────────────────────────────────────────────────

@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """テスト用に thebranch.sqlite を tmp_path に作り、最低限のテーブル構成を投入する。

    THEBRANCH_DB を一時ファイルへリダイレクトし、テスト後に元に戻す。
    """
    test_db = tmp_path / "thebranch_test.sqlite"

    # 必要最小限のスキーマ（実マイグレーションから抜粋）
    conn = sqlite3.connect(str(test_db))
    conn.executescript(
        """
        CREATE TABLE departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            parent_id INTEGER,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE team_members (
            id TEXT PRIMARY KEY,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT DEFAULT 'member',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(team_id, user_id)
        );

        CREATE TABLE cross_dept_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_dept_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
            to_dept_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
            task_name TEXT NOT NULL,
            task_description TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending', 'accepted', 'rejected')),
            created_by TEXT,
            reject_reason TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE notification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_key TEXT NOT NULL UNIQUE,
            notification_type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT DEFAULT 'info',
            recipient_id TEXT,
            recipient_type TEXT,
            source_table TEXT,
            source_id INTEGER,
            metadata TEXT,
            action_url TEXT,
            status TEXT DEFAULT 'unread',
            read_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    # シードデータ
    # 部署: 1=開発部, 2=営業部, 3=空き部署（メンバーなし）
    conn.executescript(
        """
        INSERT INTO departments (id, name, slug) VALUES
            (1, '開発部', 'dev'),
            (2, '営業部', 'sales'),
            (3, '空き部署', 'empty');

        INSERT INTO teams (id, department_id, name, slug) VALUES
            (1, 1, '開発チームA', 'dev-a'),
            (2, 2, '営業チームA', 'sales-a');

        INSERT INTO users (id, username, email) VALUES
            ('user-dev', 'dev_user', 'dev@example.com'),
            ('user-sales', 'sales_user', 'sales@example.com'),
            ('user-outsider', 'outsider', 'outsider@example.com');

        INSERT INTO team_members (id, team_id, user_id, role, status) VALUES
            ('tm-dev', 1, 'user-dev', 'member', 'active'),
            ('tm-sales', 2, 'user-sales', 'member', 'active');
        """
    )
    conn.commit()
    conn.close()

    # dashboard.app の THEBRANCH_DB をテスト DB に差し替える
    from dashboard import app as app_module

    monkeypatch.setattr(app_module, "THEBRANCH_DB", test_db)

    # ensure_db_initialized が再初期化フラグをセットしないように、フラグも初期化しておく
    if hasattr(app_module, "_db_initialized"):
        monkeypatch.setattr(app_module, "_db_initialized", True)

    yield test_db


def _override_user(user_id: str):
    """get_current_user_zero_trust を上書きするためのヘルパ"""
    async def _fake_user():
        return {
            "id": user_id,
            "username": user_id,
            "email": f"{user_id}@example.com",
            "roles": ["member"],
            "scopes": ["read", "write"],
            "token_type": "test",
        }
    return _fake_user


@pytest.fixture
def app_with_user(fresh_db):
    """user-dev として認証された FastAPI app を返す。"""
    from dashboard.app import app, get_current_user_zero_trust
    app.dependency_overrides[get_current_user_zero_trust] = _override_user("user-dev")
    yield app
    app.dependency_overrides.pop(get_current_user_zero_trust, None)


@pytest.fixture
def app_with_outsider(fresh_db):
    """部署所属なしユーザーで認証された FastAPI app を返す。"""
    from dashboard.app import app, get_current_user_zero_trust
    app.dependency_overrides[get_current_user_zero_trust] = _override_user("user-outsider")
    yield app
    app.dependency_overrides.pop(get_current_user_zero_trust, None)


@pytest.fixture
def app_with_sales(fresh_db):
    """user-sales（営業部所属）として認証された FastAPI app を返す。"""
    from dashboard.app import app, get_current_user_zero_trust
    app.dependency_overrides[get_current_user_zero_trust] = _override_user("user-sales")
    yield app
    app.dependency_overrides.pop(get_current_user_zero_trust, None)


# ─── 権限チェックヘルパのテスト ──────────────────────────────────────

@pytest.mark.asyncio
async def test_check_user_in_department_returns_true_for_member(fresh_db):
    """ユーザが対象部署に所属していれば True"""
    from dashboard.app import check_user_in_department
    assert await check_user_in_department("user-dev", 1) is True
    assert await check_user_in_department("user-sales", 2) is True


@pytest.mark.asyncio
async def test_check_user_in_department_returns_false_for_non_member(fresh_db):
    """所属していない部署では False"""
    from dashboard.app import check_user_in_department
    assert await check_user_in_department("user-dev", 2) is False
    assert await check_user_in_department("user-outsider", 1) is False


@pytest.mark.asyncio
async def test_check_user_in_department_handles_missing_args(fresh_db):
    """空引数では False（エラーは投げない）"""
    from dashboard.app import check_user_in_department
    assert await check_user_in_department("", 1) is False
    assert await check_user_in_department("user-dev", 0) is False


# ─── POST /api/departments/{dept_id}/cross-dept-tasks ─────────────

@pytest.mark.asyncio
async def test_create_cross_dept_task_success(app_with_user):
    """正常: メンバーが自部署から他部署へ依頼を作成できる"""
    async with AsyncClient(transport=ASGITransport(app=app_with_user), base_url="http://test") as client:
        resp = await client.post(
            "/api/departments/1/cross-dept-tasks",
            json={"to_dept_id": 2, "task_name": "資料レビュー依頼", "task_description": "資料を確認してください"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["from_dept_id"] == 1
    assert body["to_dept_id"] == 2
    assert body["task_name"] == "資料レビュー依頼"
    assert body["status"] == "pending"
    assert body["created_by"] == "user-dev"


@pytest.mark.asyncio
async def test_create_cross_dept_task_forbidden_non_member(app_with_outsider):
    """403: 依頼元部署のメンバーでないユーザは作成できない"""
    async with AsyncClient(transport=ASGITransport(app=app_with_outsider), base_url="http://test") as client:
        resp = await client.post(
            "/api/departments/1/cross-dept-tasks",
            json={"to_dept_id": 2, "task_name": "依頼"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_cross_dept_task_404_unknown_from_dept(app_with_user):
    """404: 依頼元部署が存在しない"""
    async with AsyncClient(transport=ASGITransport(app=app_with_user), base_url="http://test") as client:
        resp = await client.post(
            "/api/departments/9999/cross-dept-tasks",
            json={"to_dept_id": 2, "task_name": "依頼"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_cross_dept_task_404_unknown_to_dept(app_with_user):
    """404: 依頼先部署が存在しない"""
    async with AsyncClient(transport=ASGITransport(app=app_with_user), base_url="http://test") as client:
        resp = await client.post(
            "/api/departments/1/cross-dept-tasks",
            json={"to_dept_id": 9999, "task_name": "依頼"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_cross_dept_task_400_same_department(app_with_user):
    """400: 同一部署に対する依頼は拒否"""
    async with AsyncClient(transport=ASGITransport(app=app_with_user), base_url="http://test") as client:
        resp = await client.post(
            "/api/departments/1/cross-dept-tasks",
            json={"to_dept_id": 1, "task_name": "依頼"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_cross_dept_task_422_empty_task_name(app_with_user):
    """422: task_name が空"""
    async with AsyncClient(transport=ASGITransport(app=app_with_user), base_url="http://test") as client:
        resp = await client.post(
            "/api/departments/1/cross-dept-tasks",
            json={"to_dept_id": 2, "task_name": "   "},
        )
    assert resp.status_code == 422


# ─── GET /api/departments/{dept_id}/incoming-requests ──────────────

@pytest.mark.asyncio
async def test_list_incoming_requests_success(app_with_sales, fresh_db):
    """正常: 受信側部署のメンバーが受信タスク一覧を取得できる"""
    # 事前データ投入: 開発部 → 営業部 への依頼 2件（pending と accepted）
    conn = sqlite3.connect(str(fresh_db))
    conn.executescript(
        """
        INSERT INTO cross_dept_tasks (from_dept_id, to_dept_id, task_name, status, created_by)
        VALUES
            (1, 2, '依頼1', 'pending', 'user-dev'),
            (1, 2, '依頼2', 'accepted', 'user-dev');
        """
    )
    conn.commit()
    conn.close()

    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        resp = await client.get("/api/departments/2/incoming-requests")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert len(body["requests"]) == 2
    assert all(r["to_dept_id"] == 2 for r in body["requests"])


@pytest.mark.asyncio
async def test_list_incoming_requests_status_filter(app_with_sales, fresh_db):
    """status フィルタが効く"""
    conn = sqlite3.connect(str(fresh_db))
    conn.executescript(
        """
        INSERT INTO cross_dept_tasks (from_dept_id, to_dept_id, task_name, status, created_by) VALUES
            (1, 2, 'p', 'pending', 'user-dev'),
            (1, 2, 'a', 'accepted', 'user-dev'),
            (1, 2, 'r', 'rejected', 'user-dev');
        """
    )
    conn.commit()
    conn.close()

    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        resp = await client.get("/api/departments/2/incoming-requests?status=pending")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["requests"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_list_incoming_requests_403_non_member(app_with_outsider):
    """403: 受信側部署のメンバーでない場合は拒否"""
    async with AsyncClient(transport=ASGITransport(app=app_with_outsider), base_url="http://test") as client:
        resp = await client.get("/api/departments/2/incoming-requests")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_incoming_requests_404_unknown_dept(app_with_user):
    """404: 部署が存在しない"""
    async with AsyncClient(transport=ASGITransport(app=app_with_user), base_url="http://test") as client:
        resp = await client.get("/api/departments/9999/incoming-requests")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_incoming_requests_422_invalid_status(app_with_sales):
    """422: 不正な status 値"""
    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        resp = await client.get("/api/departments/2/incoming-requests?status=unknown_status")
    assert resp.status_code == 422


# ─── PUT /api/cross-dept-tasks/{task_id}/accept ────────────────────

def _seed_pending_task(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute(
        """
        INSERT INTO cross_dept_tasks (from_dept_id, to_dept_id, task_name, status, created_by)
        VALUES (1, 2, '受理テスト', 'pending', 'user-dev')
        """
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


@pytest.mark.asyncio
async def test_accept_cross_dept_task_success(app_with_sales, fresh_db):
    """正常: pending → accepted に遷移し、notification_logs に通知が記録される"""
    task_id = _seed_pending_task(fresh_db)

    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        resp = await client.put(
            f"/api/cross-dept-tasks/{task_id}/accept",
            json={"comment": "了解しました"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["id"] == task_id

    # 通知ログ確認
    conn = sqlite3.connect(str(fresh_db))
    cur = conn.execute(
        "SELECT notification_type, source_table, source_id FROM notification_logs WHERE source_id = ?",
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "collaboration_request_accepted"
    assert row[1] == "cross_dept_tasks"
    assert row[2] == task_id


@pytest.mark.asyncio
async def test_accept_cross_dept_task_403_non_member(app_with_outsider, fresh_db):
    """403: 受信側部署のメンバーでない場合"""
    task_id = _seed_pending_task(fresh_db)

    async with AsyncClient(transport=ASGITransport(app=app_with_outsider), base_url="http://test") as client:
        resp = await client.put(
            f"/api/cross-dept-tasks/{task_id}/accept",
            json={},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_accept_cross_dept_task_403_from_dept_member(app_with_user, fresh_db):
    """403: 依頼元部署メンバー（受信側ではない）は accept できない"""
    task_id = _seed_pending_task(fresh_db)

    async with AsyncClient(transport=ASGITransport(app=app_with_user), base_url="http://test") as client:
        resp = await client.put(
            f"/api/cross-dept-tasks/{task_id}/accept",
            json={},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_accept_cross_dept_task_404_not_found(app_with_sales):
    """404: タスクが存在しない"""
    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        resp = await client.put("/api/cross-dept-tasks/9999/accept", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_accept_cross_dept_task_409_already_accepted(app_with_sales, fresh_db):
    """409: 既に accepted のタスクは再度 accept できない"""
    task_id = _seed_pending_task(fresh_db)

    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        first = await client.put(f"/api/cross-dept-tasks/{task_id}/accept", json={})
        assert first.status_code == 200
        second = await client.put(f"/api/cross-dept-tasks/{task_id}/accept", json={})
    assert second.status_code == 409


# ─── PUT /api/cross-dept-tasks/{task_id}/reject ────────────────────

@pytest.mark.asyncio
async def test_reject_cross_dept_task_success(app_with_sales, fresh_db):
    """正常: pending → rejected に遷移し、reject_reason が保存される"""
    task_id = _seed_pending_task(fresh_db)

    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        resp = await client.put(
            f"/api/cross-dept-tasks/{task_id}/reject",
            json={"reason": "リソース不足"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["reject_reason"] == "リソース不足"

    # 通知ログ確認
    conn = sqlite3.connect(str(fresh_db))
    cur = conn.execute(
        "SELECT notification_type FROM notification_logs WHERE source_id = ?",
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "collaboration_request_rejected"


@pytest.mark.asyncio
async def test_reject_cross_dept_task_403_non_member(app_with_outsider, fresh_db):
    """403: 受信側部署のメンバーでない場合"""
    task_id = _seed_pending_task(fresh_db)

    async with AsyncClient(transport=ASGITransport(app=app_with_outsider), base_url="http://test") as client:
        resp = await client.put(
            f"/api/cross-dept-tasks/{task_id}/reject",
            json={"reason": "no"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reject_cross_dept_task_404(app_with_sales):
    """404: タスクが存在しない"""
    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        resp = await client.put("/api/cross-dept-tasks/9999/reject", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_cross_dept_task_409_already_rejected(app_with_sales, fresh_db):
    """409: 既に rejected のタスクは再度 reject できない"""
    task_id = _seed_pending_task(fresh_db)

    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        first = await client.put(f"/api/cross-dept-tasks/{task_id}/reject", json={"reason": "x"})
        assert first.status_code == 200
        second = await client.put(f"/api/cross-dept-tasks/{task_id}/reject", json={"reason": "y"})
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_accept_then_reject_returns_409(app_with_sales, fresh_db):
    """409: accepted 済みタスクを reject しようとすると拒否される"""
    task_id = _seed_pending_task(fresh_db)

    async with AsyncClient(transport=ASGITransport(app=app_with_sales), base_url="http://test") as client:
        accept = await client.put(f"/api/cross-dept-tasks/{task_id}/accept", json={})
        assert accept.status_code == 200
        reject = await client.put(f"/api/cross-dept-tasks/{task_id}/reject", json={"reason": "やっぱり"})
    assert reject.status_code == 409


# ─── 認証なし（dependency override 解除）──────────────────────────

@pytest.mark.asyncio
async def test_unauthorized_returns_401(fresh_db):
    """Authorization ヘッダなしの場合は 401 を返す（dependency_overrides 適用なし）"""
    from dashboard.app import app, get_current_user_zero_trust
    # オーバーライドが残らないよう明示的に空にしておく
    app.dependency_overrides.pop(get_current_user_zero_trust, None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/departments/1/cross-dept-tasks",
            json={"to_dept_id": 2, "task_name": "x"},
        )
    assert resp.status_code == 401
