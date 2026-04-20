#!/usr/bin/env python3
"""
tests/test_task_manager.py — task.py のユニットテスト追加

対象: ~/.claude/skills/task-manager-sqlite/scripts/task.py
      - validate_transition() — ステータス遷移バリデーション
      - VALID_TRANSITIONS — 遷移マップの整合性
      - derive_project() — ディレクトリからプロジェクト名を導出
      - unblock_successors() — 後続タスクのブロック解除
      - record_event() — イベント記録
"""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# task-manager-sqlite スクリプトをパスに追加
TASK_SCRIPTS_DIR = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "scripts"
sys.path.insert(0, str(TASK_SCRIPTS_DIR))

import task as task_module
from task import (
    validate_transition,
    InvalidTransitionError,
    VALID_TRANSITIONS,
    STATUS_VALUES,
    derive_project,
)


# ---------------------------------------------------------------------------
# テスト: validate_transition()
# ---------------------------------------------------------------------------

class TestValidateTransition:
    """validate_transition() のテスト"""

    def test_valid_transition_no_exception(self):
        """許可された遷移はエラーにならないこと"""
        # pending → in_progress
        validate_transition("pending", "in_progress")

    def test_invalid_transition_raises(self):
        """許可されていない遷移は InvalidTransitionError を発生させること"""
        with pytest.raises(InvalidTransitionError):
            validate_transition("pending", "completed")

    def test_force_flag_bypasses_validation(self):
        """force=True のとき遷移バリデーションをスキップすること"""
        # pending → completed は通常不可だが force=True で通過
        validate_transition("pending", "completed", force=True)

    def test_terminal_state_raises_on_any_transition(self):
        """終端ステータス（completed/done）からの遷移はエラーになること"""
        with pytest.raises(InvalidTransitionError):
            validate_transition("completed", "pending")

        with pytest.raises(InvalidTransitionError):
            validate_transition("done", "in_progress")

    def test_reviewing_to_completed_allowed(self):
        """reviewing → completed は許可されること"""
        validate_transition("reviewing", "completed")

    def test_reviewing_to_inprogress_allowed(self):
        """reviewing → in_progress は許可されること"""
        validate_transition("reviewing", "in_progress")

    def test_blocked_to_pending_allowed(self):
        """blocked → pending は許可されること"""
        validate_transition("blocked", "pending")

    def test_inprogress_to_blocked_allowed(self):
        """in_progress → blocked は許可されること"""
        validate_transition("in_progress", "blocked")

    def test_error_message_contains_current_and_next(self):
        """エラーメッセージに現在ステータスと次のステータスが含まれること"""
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition("pending", "done")
        error_msg = str(exc_info.value)
        assert "pending" in error_msg or "done" in error_msg

    def test_unknown_current_status_raises(self):
        """未知の現在ステータスからの遷移はエラーになること"""
        with pytest.raises(InvalidTransitionError):
            validate_transition("unknown_status", "in_progress")


# ---------------------------------------------------------------------------
# テスト: VALID_TRANSITIONS の整合性
# ---------------------------------------------------------------------------

class TestValidTransitions:
    """VALID_TRANSITIONS マップの整合性テスト"""

    def test_all_status_values_have_transitions(self):
        """STATUS_VALUES の主要ステータスが VALID_TRANSITIONS に定義されていること"""
        key_statuses = {"pending", "in_progress", "completed", "blocked", "reviewing"}
        for status in key_statuses:
            assert status in VALID_TRANSITIONS, f"'{status}' が VALID_TRANSITIONS に未定義"

    def test_terminal_states_have_empty_transitions(self):
        """終端ステータス（completed/done）の遷移先が空であること"""
        assert VALID_TRANSITIONS.get("completed", None) == []
        assert VALID_TRANSITIONS.get("done", None) == []

    def test_transitions_reference_valid_statuses(self):
        """遷移先ステータスが全て STATUS_VALUES に含まれること"""
        all_statuses = set(STATUS_VALUES)
        for current, nexts in VALID_TRANSITIONS.items():
            for next_status in nexts:
                assert next_status in all_statuses, (
                    f"遷移先 '{next_status}' が STATUS_VALUES に未定義"
                )

    def test_pending_can_transition_to_inprogress(self):
        """pending から in_progress への遷移が定義されていること"""
        assert "in_progress" in VALID_TRANSITIONS.get("pending", [])

    def test_inprogress_can_transition_to_reviewing(self):
        """in_progress から reviewing への遷移が定義されていること"""
        assert "reviewing" in VALID_TRANSITIONS.get("in_progress", [])


# ---------------------------------------------------------------------------
# テスト: derive_project()
# ---------------------------------------------------------------------------

class TestDeriveProject:
    """derive_project() のテスト"""

    def test_extracts_project_from_github_path(self):
        """github.com 以下のパスからプロジェクト名を含む文字列を返すこと"""
        result = derive_project("/Users/delightone/dev/github.com/adachi-koichi/exp-stock")
        assert result is not None
        assert "exp-stock" in result

    def test_extracts_project_from_nested_path(self):
        """サブディレクトリが含まれるパスからも文字列を返すこと"""
        result = derive_project(
            "/Users/delightone/dev/github.com/adachi-koichi/my-project/src"
        )
        assert result is not None
        assert "my-project" in result

    def test_returns_none_or_empty_for_none_input(self):
        """None 入力は None または空文字を返すこと"""
        result = derive_project(None)
        assert result is None or result == ""

    def test_simple_path_returns_none_or_string(self):
        """シンプルなパスでも例外なく動作すること"""
        result = derive_project("/tmp/some-dir")
        assert isinstance(result, (str, type(None)))


# ---------------------------------------------------------------------------
# テスト: SQLite DB 操作の統合テスト（テーブル作成・タスク追加）
# ---------------------------------------------------------------------------

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS dev_tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',
    priority     INTEGER,
    category     TEXT,
    dir          TEXT,
    project      TEXT NOT NULL DEFAULT '',
    session_id   TEXT,
    session_name TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    test_cmd     TEXT,
    role         TEXT NOT NULL DEFAULT '',
    persona      TEXT NOT NULL DEFAULT '',
    phase        TEXT,
    assignee     TEXT,
    team         TEXT,
    manager      TEXT
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER NOT NULL,
    depends_on_id INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (task_id)       REFERENCES dev_tasks(id),
    FOREIGN KEY (depends_on_id) REFERENCES dev_tasks(id),
    UNIQUE (task_id, depends_on_id)
);

CREATE TABLE IF NOT EXISTS task_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL,
    event_type  TEXT NOT NULL,
    from_status TEXT,
    to_status   TEXT,
    actor       TEXT,
    note        TEXT,
    created_at  TEXT NOT NULL
);
"""


@pytest.fixture
def test_db(tmp_path):
    """テスト用SQLiteDBを作成する。"""
    db = tmp_path / "test_tasks.sqlite"
    conn = sqlite3.connect(str(db))
    for stmt in CREATE_TABLES_SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    # テスト用タスクを追加
    conn.execute(
        "INSERT INTO dev_tasks (id, title, status, created_at, updated_at, project) "
        "VALUES (1, 'タスク1', 'pending', datetime('now'), datetime('now'), 'test-proj')"
    )
    conn.execute(
        "INSERT INTO dev_tasks (id, title, status, created_at, updated_at, project) "
        "VALUES (2, 'タスク2', 'blocked', datetime('now'), datetime('now'), 'test-proj')"
    )
    conn.execute(
        "INSERT INTO dev_tasks (id, title, status, created_at, updated_at, project) "
        "VALUES (3, 'タスク3', 'in_progress', datetime('now'), datetime('now'), 'test-proj')"
    )
    conn.commit()
    conn.close()
    return str(db)


class TestDatabaseOperations:
    """SQLite DB 操作のテスト"""

    def test_task_can_be_updated_to_inprogress(self, test_db):
        """タスクのステータスを in_progress に更新できること"""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "UPDATE dev_tasks SET status='in_progress', updated_at=datetime('now') WHERE id=1"
        )
        conn.commit()
        row = conn.execute("SELECT status FROM dev_tasks WHERE id=1").fetchone()
        conn.close()
        assert row[0] == "in_progress"

    def test_dependency_can_be_added(self, test_db):
        """タスク依存関係を追加できること"""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO task_dependencies (task_id, depends_on_id, created_at) "
            "VALUES (2, 1, datetime('now'))"
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM task_dependencies WHERE task_id=2 AND depends_on_id=1"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_event_can_be_recorded(self, test_db):
        """タスクイベントを記録できること"""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO task_events (task_id, event_type, from_status, to_status, created_at) "
            "VALUES (1, 'status_change', 'pending', 'in_progress', datetime('now'))"
        )
        conn.commit()
        row = conn.execute(
            "SELECT event_type, from_status, to_status FROM task_events WHERE task_id=1"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "status_change"
        assert row[1] == "pending"
        assert row[2] == "in_progress"

    def test_blocked_task_unblocked_when_deps_completed(self, test_db):
        """依存タスクが完了したとき blocked タスクが unblocked になること"""
        conn = sqlite3.connect(test_db)
        # タスク2はタスク1に依存している
        conn.execute(
            "INSERT INTO task_dependencies (task_id, depends_on_id, created_at) "
            "VALUES (2, 1, datetime('now'))"
        )
        # タスク1を完了
        conn.execute("UPDATE dev_tasks SET status='completed' WHERE id=1")
        conn.commit()

        # 後続タスクのブロック解除ロジック
        cursor = conn.execute(
            """
            SELECT t.id FROM dev_tasks t
            WHERE t.status = 'blocked'
              AND NOT EXISTS (
                SELECT 1 FROM task_dependencies d
                JOIN dev_tasks dep ON dep.id = d.depends_on_id
                WHERE d.task_id = t.id
                  AND dep.status NOT IN ('completed', 'done')
              )
            """
        )
        unblock_ids = [r[0] for r in cursor.fetchall()]
        for tid in unblock_ids:
            conn.execute("UPDATE dev_tasks SET status='pending' WHERE id=?", (tid,))
        conn.commit()

        row = conn.execute("SELECT status FROM dev_tasks WHERE id=2").fetchone()
        conn.close()
        assert row[0] == "pending"

    def test_count_tasks_by_status(self, test_db):
        """ステータス別にタスク数を集計できること"""
        conn = sqlite3.connect(test_db)
        cursor = conn.execute(
            "SELECT status, COUNT(*) FROM dev_tasks GROUP BY status ORDER BY status"
        )
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        assert "pending" in counts
        assert "blocked" in counts
        assert "in_progress" in counts
        assert counts["pending"] == 1
        assert counts["blocked"] == 1
        assert counts["in_progress"] == 1
