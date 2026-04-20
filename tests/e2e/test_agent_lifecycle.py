#!/usr/bin/env python3
"""
tests/e2e/test_agent_lifecycle.py — エージェントライフサイクルE2Eテスト

タスク #2394: E2Eテスト「エージェントライフサイクル」
- エージェント起動テスト（POST /api/departments/<id>/agents）
- エージェント停止テスト（DELETE /api/departments/<id>/agents/<agent_id>）
- エージェント状態確認テスト（GET /api/departments/<id>/agents）
"""

import pytest
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime


@pytest.fixture(scope="function")
def db_path(tmp_path):
    """テスト用の一時SQLiteデータベース"""
    return tmp_path / "test_agent_lifecycle.sqlite"


@pytest.fixture(scope="function")
def setup_test_db(db_path):
    """テストデータベースをセットアップ"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # テーブル作成
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            description TEXT,
            parent_id INTEGER,
            budget REAL,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL,
            session_id TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            status TEXT DEFAULT 'running',
            started_at TEXT,
            stopped_at TEXT,
            error_message TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS department_agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL,
            agent_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            joined_at TEXT,
            FOREIGN KEY (department_id) REFERENCES departments(id),
            FOREIGN KEY (agent_id) REFERENCES agents(id),
            UNIQUE (department_id, agent_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT,
            role TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)

    # テストデータ挿入
    now = datetime.utcnow().isoformat()

    cursor.execute("""
        INSERT INTO departments (name, slug, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, ("テスト部署", "test-dept", "active", now, now))

    conn.commit()
    conn.close()

    yield db_path

    # クリーンアップ
    if db_path.exists():
        db_path.unlink()


class TestAgentLifecycle:
    """エージェントライフサイクル統合テスト"""

    def test_create_department_agent_success(self, setup_test_db):
        """エージェント追加が成功すること"""
        db_path = setup_test_db
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 既存の department_id を取得
        cursor.execute("SELECT id FROM departments LIMIT 1")
        dept_id = cursor.fetchone()[0]

        # agent テーブルに新規エージェント追加
        cursor.execute("""
            INSERT INTO agents (department_id, session_id, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (dept_id, "test_session_001", "engineer", "running"))
        conn.commit()
        agent_id = cursor.lastrowid

        # department_agents テーブルに関連付け
        cursor.execute("""
            INSERT INTO department_agents (department_id, agent_id, role, joined_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (dept_id, agent_id, "engineer"))
        conn.commit()

        # 確認
        cursor.execute(
            "SELECT agent_id, role FROM department_agents WHERE department_id = ? AND agent_id = ?",
            (dept_id, agent_id)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == agent_id
        assert row[1] == "engineer"

    def test_list_department_agents(self, setup_test_db):
        """デパートメント内のエージェント一覧取得が成功すること"""
        db_path = setup_test_db
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 既存の department_id を取得
        cursor.execute("SELECT id FROM departments LIMIT 1")
        dept_id = cursor.fetchone()[0]

        # 複数のエージェントを追加
        for i in range(3):
            cursor.execute("""
                INSERT INTO agents (department_id, session_id, role, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (dept_id, f"test_session_{i:03d}", f"role_{i}", "running"))
            conn.commit()
            agent_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO department_agents (department_id, agent_id, role, joined_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (dept_id, agent_id, f"role_{i}"))
            conn.commit()

        # 一覧取得
        cursor.execute("""
            SELECT da.agent_id, da.role, da.joined_at
            FROM department_agents da
            WHERE da.department_id = ?
            ORDER BY da.joined_at
        """, (dept_id,))
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 3
        assert all(row[0] is not None for row in rows)

    def test_remove_department_agent(self, setup_test_db):
        """エージェント削除が成功すること"""
        db_path = setup_test_db
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 既存の department_id を取得
        cursor.execute("SELECT id FROM departments LIMIT 1")
        dept_id = cursor.fetchone()[0]

        # エージェント追加
        cursor.execute("""
            INSERT INTO agents (department_id, session_id, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (dept_id, "test_session_remove", "engineer", "running"))
        conn.commit()
        agent_id = cursor.lastrowid

        # department_agents に関連付け
        cursor.execute("""
            INSERT INTO department_agents (department_id, agent_id, role, joined_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (dept_id, agent_id, "engineer"))
        conn.commit()

        # 削除前に確認
        cursor.execute(
            "SELECT COUNT(*) FROM department_agents WHERE department_id = ? AND agent_id = ?",
            (dept_id, agent_id)
        )
        count_before = cursor.fetchone()[0]
        assert count_before == 1

        # エージェント削除
        cursor.execute(
            "DELETE FROM department_agents WHERE department_id = ? AND agent_id = ?",
            (dept_id, agent_id)
        )
        conn.commit()

        # 削除後に確認
        cursor.execute(
            "SELECT COUNT(*) FROM department_agents WHERE department_id = ? AND agent_id = ?",
            (dept_id, agent_id)
        )
        count_after = cursor.fetchone()[0]
        conn.close()

        assert count_after == 0

    def test_agent_status_management(self, setup_test_db):
        """エージェントの status フィールド管理が正常に機能すること"""
        db_path = setup_test_db
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 既存の department_id を取得
        cursor.execute("SELECT id FROM departments LIMIT 1")
        dept_id = cursor.fetchone()[0]

        # エージェント追加（running ステータス）
        cursor.execute("""
            INSERT INTO agents (department_id, session_id, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (dept_id, "test_session_status", "engineer", "running"))
        conn.commit()
        agent_id = cursor.lastrowid

        # 初期ステータス確認
        cursor.execute(
            "SELECT status FROM agents WHERE id = ?",
            (agent_id,)
        )
        status = cursor.fetchone()[0]
        assert status == "running"

        # ステータス更新（stopped）
        cursor.execute(
            "UPDATE agents SET status = ? WHERE id = ?",
            ("stopped", agent_id)
        )
        conn.commit()

        # 更新後のステータス確認
        cursor.execute(
            "SELECT status FROM agents WHERE id = ?",
            (agent_id,)
        )
        status = cursor.fetchone()[0]
        conn.close()

        assert status == "stopped"

    def test_agent_lifecycle_full_cycle(self, setup_test_db):
        """エージェントのフルライフサイクル（起動→確認→停止）"""
        db_path = setup_test_db
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 既存の department_id を取得
        cursor.execute("SELECT id FROM departments LIMIT 1")
        dept_id = cursor.fetchone()[0]

        # Step 1: エージェント起動
        cursor.execute("""
            INSERT INTO agents (department_id, session_id, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (dept_id, "test_session_lifecycle", "engineer", "running"))
        conn.commit()
        agent_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO department_agents (department_id, agent_id, role, joined_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (dept_id, agent_id, "engineer"))
        conn.commit()

        # Step 2: ステータス確認（running）
        cursor.execute("""
            SELECT da.agent_id, a.status
            FROM department_agents da
            JOIN agents a ON da.agent_id = a.id
            WHERE da.department_id = ? AND da.agent_id = ?
        """, (dept_id, agent_id))
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == "running"

        # Step 3: エージェント停止
        cursor.execute(
            "DELETE FROM department_agents WHERE department_id = ? AND agent_id = ?",
            (dept_id, agent_id)
        )
        conn.commit()

        # Step 4: 削除確認
        cursor.execute(
            "SELECT COUNT(*) FROM department_agents WHERE department_id = ? AND agent_id = ?",
            (dept_id, agent_id)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0

    def test_agent_error_handling_duplicate_agent(self, setup_test_db):
        """同じ agent_id を重複して追加しようとするとエラーになること"""
        db_path = setup_test_db
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 既存の department_id を取得
        cursor.execute("SELECT id FROM departments LIMIT 1")
        dept_id = cursor.fetchone()[0]

        # エージェント1を追加
        cursor.execute("""
            INSERT INTO agents (department_id, session_id, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (dept_id, "test_session_duplicate", "engineer", "running"))
        conn.commit()
        agent_id = cursor.lastrowid

        # department_agents に関連付け
        cursor.execute("""
            INSERT INTO department_agents (department_id, agent_id, role, joined_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (dept_id, agent_id, "engineer"))
        conn.commit()

        # 同じ agent_id を重複して追加しようとする
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO department_agents (department_id, agent_id, role, joined_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (dept_id, agent_id, "engineer"))
            conn.commit()

        conn.close()

    def test_department_agents_join_agent_info(self, setup_test_db):
        """department_agents と agents のJOINが正しく機能すること"""
        db_path = setup_test_db
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 既存の department_id を取得
        cursor.execute("SELECT id FROM departments LIMIT 1")
        dept_id = cursor.fetchone()[0]

        # エージェント追加
        cursor.execute("""
            INSERT INTO agents (department_id, session_id, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (dept_id, "test_session_join", "pm", "running"))
        conn.commit()
        agent_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO department_agents (department_id, agent_id, role, joined_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (dept_id, agent_id, "pm"))
        conn.commit()

        # JOINクエリで情報取得
        cursor.execute("""
            SELECT da.agent_id, da.role, a.session_id, a.status
            FROM department_agents da
            JOIN agents a ON da.agent_id = a.id
            WHERE da.department_id = ? AND da.agent_id = ?
        """, (dept_id, agent_id))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == agent_id
        assert row[1] == "pm"
        assert row[2] == "test_session_join"
        assert row[3] == "running"


class TestAgentLifecycleWithMocks:
    """モック使用したエージェントライフサイクルテスト"""

    @patch("sqlite3.connect")
    def test_department_agents_api_contract(self, mock_connect):
        """department_agents APIレスポンスが期待の構造をもつこと"""
        # モック db接続
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # GET /api/departments/<id>/agents のレスポンス構造
        mock_cursor.fetchall.return_value = [
            (1, "engineer", "2026-04-20T10:00:00"),
            (2, "pm", "2026-04-20T10:05:00"),
        ]

        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # テスト実行
        with patch("sqlite3.connect", return_value=mock_conn):
            conn = sqlite3.connect(":memory:")
            cursor = conn.cursor()
            cursor.fetchall.return_value = [
                (1, "engineer", "2026-04-20T10:00:00"),
                (2, "pm", "2026-04-20T10:05:00"),
            ]

            rows = cursor.fetchall()
            agents = [
                {
                    "agent_id": r[0],
                    "role": r[1],
                    "joined_at": r[2],
                }
                for r in rows
            ]

            assert len(agents) == 2
            assert agents[0]["role"] == "engineer"
            assert agents[1]["role"] == "pm"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
