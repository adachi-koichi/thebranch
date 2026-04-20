#!/usr/bin/env python3
"""
tests/test_task_completion.py — check_task_completion.py のユニットテスト
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_task_completion import (
    check_task_completion,
    get_completed_tasks,
    get_conn,
    get_task_by_id,
    get_tasks_by_session,
    get_tasks_by_status,
)


# ---------------------------------------------------------------------------
# テスト用のインメモリSQLiteフィクスチャ
# ---------------------------------------------------------------------------

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS dev_tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    priority    INTEGER,
    category    TEXT,
    dir         TEXT,
    project     TEXT,
    session_id  TEXT,
    session_name TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    test_cmd    TEXT
);
"""

SAMPLE_TASKS = [
    (1, "タスクA", "説明A", "completed", 1, "infra", "/path/a", "proj-a", "sid1", "session-a", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", None),
    (2, "タスクB", "説明B", "in_progress", 2, "frontend", "/path/b", "proj-b", "sid2", "session-b", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", None),
    (3, "タスクC", None, "pending", None, None, None, None, None, "session-a", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", None),
    (4, "タスクD", "説明D", "done", 1, "test", "/path/d", "proj-d", "sid4", "session-c", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "pytest tests/"),
]


@pytest.fixture
def db_path(tmp_path):
    """テスト用の一時SQLiteデータベースを作成する。"""
    db = tmp_path / "test_tasks.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(CREATE_TABLE)
    conn.executemany(
        "INSERT INTO dev_tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        SAMPLE_TASKS,
    )
    conn.commit()
    conn.close()
    return str(db)


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------

class TestGetConn:
    """get_conn() のテスト"""

    def test_returns_connection(self, db_path):
        conn = get_conn(db_path)
        assert conn is not None
        conn.close()

    def test_row_factory(self, db_path):
        conn = get_conn(db_path)
        row = conn.execute("SELECT * FROM dev_tasks WHERE id = 1").fetchone()
        assert row["title"] == "タスクA"
        conn.close()


class TestGetTaskById:
    """get_task_by_id() のテスト"""

    def test_existing_task(self, db_path):
        task = get_task_by_id(1, db_path)
        assert task is not None
        assert task["id"] == 1
        assert task["title"] == "タスクA"
        assert task["status"] == "completed"

    def test_nonexistent_task(self, db_path):
        task = get_task_by_id(9999, db_path)
        assert task is None

    def test_in_progress_task(self, db_path):
        task = get_task_by_id(2, db_path)
        assert task["status"] == "in_progress"


class TestGetTasksBySession:
    """get_tasks_by_session() のテスト"""

    def test_session_with_tasks(self, db_path):
        tasks = get_tasks_by_session("session-a", db_path)
        assert len(tasks) == 2
        ids = [t["id"] for t in tasks]
        assert 1 in ids
        assert 3 in ids

    def test_session_without_tasks(self, db_path):
        tasks = get_tasks_by_session("nonexistent-session", db_path)
        assert tasks == []

    def test_session_b(self, db_path):
        tasks = get_tasks_by_session("session-b", db_path)
        assert len(tasks) == 1
        assert tasks[0]["id"] == 2


class TestGetTasksByStatus:
    """get_tasks_by_status() のテスト"""

    def test_completed_tasks(self, db_path):
        tasks = get_tasks_by_status("completed", db_path)
        assert len(tasks) == 1
        assert tasks[0]["id"] == 1

    def test_in_progress_tasks(self, db_path):
        tasks = get_tasks_by_status("in_progress", db_path)
        assert len(tasks) == 1
        assert tasks[0]["id"] == 2

    def test_pending_tasks(self, db_path):
        tasks = get_tasks_by_status("pending", db_path)
        assert len(tasks) == 1
        assert tasks[0]["id"] == 3

    def test_nonexistent_status(self, db_path):
        tasks = get_tasks_by_status("nonexistent", db_path)
        assert tasks == []


class TestGetCompletedTasks:
    """get_completed_tasks() のテスト"""

    def test_all_completed(self, db_path):
        tasks = get_completed_tasks(db_path=db_path)
        # completed と done の両方が含まれる
        assert len(tasks) == 2
        statuses = {t["status"] for t in tasks}
        assert "completed" in statuses
        assert "done" in statuses

    def test_filter_by_session(self, db_path):
        tasks = get_completed_tasks(session_name="session-a", db_path=db_path)
        assert len(tasks) == 1
        assert tasks[0]["id"] == 1
        assert tasks[0]["status"] == "completed"

    def test_filter_by_nonexistent_session(self, db_path):
        tasks = get_completed_tasks(session_name="ghost-session", db_path=db_path)
        assert tasks == []


class TestCheckTaskCompletion:
    """check_task_completion() のテスト"""

    def test_completed_task(self, db_path):
        result = check_task_completion(1, db_path)
        assert result["task_id"] == 1
        assert result["title"] == "タスクA"
        assert result["status"] == "completed"
        assert result["is_completed"] is True

    def test_done_task(self, db_path):
        result = check_task_completion(4, db_path)
        assert result["is_completed"] is True
        assert result["status"] == "done"

    def test_in_progress_task(self, db_path):
        result = check_task_completion(2, db_path)
        assert result["task_id"] == 2
        assert result["is_completed"] is False
        assert result["status"] == "in_progress"

    def test_pending_task(self, db_path):
        result = check_task_completion(3, db_path)
        assert result["is_completed"] is False
        assert result["status"] == "pending"

    def test_nonexistent_task(self, db_path):
        result = check_task_completion(9999, db_path)
        assert result["is_completed"] is False
        assert "error" in result
        assert result["title"] is None

    def test_result_has_dir(self, db_path):
        result = check_task_completion(1, db_path)
        assert result["dir"] == "/path/a"

    def test_result_has_session_name(self, db_path):
        result = check_task_completion(1, db_path)
        assert result["session_name"] == "session-a"
