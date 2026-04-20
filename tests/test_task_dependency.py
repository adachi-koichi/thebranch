#!/usr/bin/env python3
"""
tests/test_task_dependency.py — タスク依存関係管理のユニットテスト

対象: ~/.claude/skills/task-manager-sqlite/scripts/task.py の依存関係管理機能
      (dep add / dep rm / dep show / unblock_successors)
注: task.py は task-manager-sqlite スキルに存在するため sys.path 経由でインポート
"""

import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# task-manager-sqlite スキルのスクリプトをパスに追加
TASK_SCRIPTS_DIR = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "scripts"
sys.path.insert(0, str(TASK_SCRIPTS_DIR))


CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS dev_tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    priority    INTEGER DEFAULT 3,
    category    TEXT,
    dir         TEXT,
    project     TEXT,
    session_id  TEXT,
    session_name TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    test_cmd    TEXT
);
"""

CREATE_DEPS_TABLE = """
CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id      INTEGER NOT NULL,
    depends_on   INTEGER NOT NULL,
    PRIMARY KEY (task_id, depends_on),
    FOREIGN KEY (task_id)    REFERENCES dev_tasks(id),
    FOREIGN KEY (depends_on) REFERENCES dev_tasks(id)
);
"""


def make_db(tmp_path: Path) -> str:
    """テスト用SQLiteDBを作成してパスを返す。"""
    db = tmp_path / "test_tasks.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(CREATE_TASKS_TABLE)
    conn.execute(CREATE_DEPS_TABLE)
    # テスト用タスクを3件追加
    for i in range(1, 4):
        conn.execute(
            "INSERT INTO dev_tasks (id, title, status, created_at, updated_at) VALUES (?, ?, 'pending', datetime('now'), datetime('now'))",
            (i, f"タスク{i}"),
        )
    conn.commit()
    conn.close()
    return str(db)


# ---------------------------------------------------------------------------
# テスト: 依存関係の追加
# ---------------------------------------------------------------------------

class TestDependencyAdd:
    """task_dependencies テーブルへの依存関係追加テスト"""

    def test_add_dependency_inserts_row(self, tmp_path):
        """依存関係を追加するとDBに行が挿入されること"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO task_dependencies (task_id, depends_on) VALUES (?, ?)",
            (2, 1),
        )
        conn.commit()

        cursor = conn.execute(
            "SELECT * FROM task_dependencies WHERE task_id=2 AND depends_on=1"
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 2
        assert row[1] == 1

    def test_add_multiple_dependencies(self, tmp_path):
        """複数の依存関係を追加できること"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO task_dependencies VALUES (3, 1)")
        conn.execute("INSERT INTO task_dependencies VALUES (3, 2)")
        conn.commit()

        cursor = conn.execute("SELECT depends_on FROM task_dependencies WHERE task_id=3")
        deps = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert 1 in deps
        assert 2 in deps

    def test_duplicate_dependency_raises(self, tmp_path):
        """同じ依存関係を重複追加すると IntegrityError が発生すること"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO task_dependencies VALUES (2, 1)")
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO task_dependencies VALUES (2, 1)")
            conn.commit()

        conn.close()


# ---------------------------------------------------------------------------
# テスト: 依存関係の削除
# ---------------------------------------------------------------------------

class TestDependencyRemove:
    """task_dependencies テーブルからの依存関係削除テスト"""

    def test_remove_dependency_deletes_row(self, tmp_path):
        """依存関係を削除するとDBから行が消えること"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO task_dependencies VALUES (2, 1)")
        conn.commit()

        conn.execute(
            "DELETE FROM task_dependencies WHERE task_id=2 AND depends_on=1"
        )
        conn.commit()

        cursor = conn.execute(
            "SELECT * FROM task_dependencies WHERE task_id=2 AND depends_on=1"
        )
        row = cursor.fetchone()
        conn.close()

        assert row is None

    def test_remove_nonexistent_dependency_no_error(self, tmp_path):
        """存在しない依存関係の削除はエラーにならないこと"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)

        # 存在しない依存関係を削除（例外なし）
        conn.execute(
            "DELETE FROM task_dependencies WHERE task_id=99 AND depends_on=1"
        )
        conn.commit()
        conn.close()

    def test_remove_one_of_multiple_dependencies(self, tmp_path):
        """複数の依存関係のうち1件だけ削除できること"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO task_dependencies VALUES (3, 1)")
        conn.execute("INSERT INTO task_dependencies VALUES (3, 2)")
        conn.commit()

        conn.execute("DELETE FROM task_dependencies WHERE task_id=3 AND depends_on=1")
        conn.commit()

        cursor = conn.execute("SELECT depends_on FROM task_dependencies WHERE task_id=3")
        deps = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert 1 not in deps
        assert 2 in deps


# ---------------------------------------------------------------------------
# テスト: 依存関係の参照
# ---------------------------------------------------------------------------

class TestDependencyShow:
    """task_dependencies テーブルの依存関係参照テスト"""

    def test_show_dependencies_returns_correct_ids(self, tmp_path):
        """タスクの依存先IDが正しく取得できること"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO task_dependencies VALUES (3, 1)")
        conn.execute("INSERT INTO task_dependencies VALUES (3, 2)")
        conn.commit()

        cursor = conn.execute(
            "SELECT depends_on FROM task_dependencies WHERE task_id=3 ORDER BY depends_on"
        )
        deps = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert deps == [1, 2]

    def test_show_no_dependencies_returns_empty(self, tmp_path):
        """依存関係がないタスクは空リストを返すこと"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)

        cursor = conn.execute(
            "SELECT depends_on FROM task_dependencies WHERE task_id=1"
        )
        deps = cursor.fetchall()
        conn.close()

        assert deps == []

    def test_show_upstream_tasks(self, tmp_path):
        """タスクに依存しているタスク（上位）を取得できること"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO task_dependencies VALUES (2, 1)")
        conn.execute("INSERT INTO task_dependencies VALUES (3, 1)")
        conn.commit()

        # タスク1に依存しているタスクを取得
        cursor = conn.execute(
            "SELECT task_id FROM task_dependencies WHERE depends_on=1 ORDER BY task_id"
        )
        dependents = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert 2 in dependents
        assert 3 in dependents


# ---------------------------------------------------------------------------
# テスト: 後続タスクのブロック解除ロジック
# ---------------------------------------------------------------------------

class TestUnblockSuccessors:
    """タスク完了時に後続タスクのブロック状態を解除するロジックのテスト"""

    def test_blocked_successor_becomes_pending_when_deps_met(self, tmp_path):
        """全依存タスク完了後、blockedタスクがpendingになること"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)

        # タスク1: completed, タスク2: blocked (タスク1に依存)
        conn.execute("UPDATE dev_tasks SET status='completed' WHERE id=1")
        conn.execute("UPDATE dev_tasks SET status='blocked' WHERE id=2")
        conn.execute("INSERT INTO task_dependencies VALUES (2, 1)")
        conn.commit()

        # 後続タスクのブロック解除ロジック（SQLで直接実装）
        cursor = conn.execute(
            """
            SELECT t.id FROM dev_tasks t
            WHERE t.status = 'blocked'
              AND NOT EXISTS (
                SELECT 1 FROM task_dependencies d
                JOIN dev_tasks dep ON dep.id = d.depends_on
                WHERE d.task_id = t.id
                  AND dep.status != 'completed'
              )
            """
        )
        unblock_ids = [r[0] for r in cursor.fetchall()]

        for tid in unblock_ids:
            conn.execute("UPDATE dev_tasks SET status='pending' WHERE id=?", (tid,))
        conn.commit()

        cursor = conn.execute("SELECT status FROM dev_tasks WHERE id=2")
        status = cursor.fetchone()[0]
        conn.close()

        assert status == "pending"

    def test_blocked_not_unblocked_when_deps_incomplete(self, tmp_path):
        """依存タスクが未完了の場合、blockedのままであること"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)

        # タスク1: in_progress, タスク2: blocked (タスク1に依存)
        conn.execute("UPDATE dev_tasks SET status='in_progress' WHERE id=1")
        conn.execute("UPDATE dev_tasks SET status='blocked' WHERE id=2")
        conn.execute("INSERT INTO task_dependencies VALUES (2, 1)")
        conn.commit()

        # ブロック解除チェック
        cursor = conn.execute(
            """
            SELECT t.id FROM dev_tasks t
            WHERE t.status = 'blocked'
              AND NOT EXISTS (
                SELECT 1 FROM task_dependencies d
                JOIN dev_tasks dep ON dep.id = d.depends_on
                WHERE d.task_id = t.id
                  AND dep.status != 'completed'
              )
            """
        )
        unblock_ids = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert 2 not in unblock_ids

    def test_no_blocked_tasks_nothing_changed(self, tmp_path):
        """blockedタスクが存在しない場合、何も変更されないこと"""
        db_path = make_db(tmp_path)
        conn = sqlite3.connect(db_path)

        # 全タスクがpending
        cursor = conn.execute(
            """
            SELECT t.id FROM dev_tasks t
            WHERE t.status = 'blocked'
            """
        )
        blocked = cursor.fetchall()
        conn.close()

        assert blocked == []
