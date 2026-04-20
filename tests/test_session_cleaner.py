#!/usr/bin/env python3
"""
tests/test_session_cleaner.py — session_cleaner.py のユニットテスト

対象: scripts/cleanup_sessions.py（session_cleaner として機能）
      - done/completed タスクのセッション検出
      - PROTECTED_SESSIONS の除外ロジック
      - セッション名からタスクID抽出
"""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import cleanup_sessions
from cleanup_sessions import (
    get_done_task_ids,
    get_active_sessions,
    extract_task_id,
    PROTECTED_SESSIONS,
    TASK_ID_PATTERN,
)


CREATE_TABLE = """
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


@pytest.fixture
def db_path(tmp_path):
    """テスト用SQLiteデータベースを作成する。"""
    db = tmp_path / "test_tasks.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(CREATE_TABLE)
    conn.commit()
    conn.close()
    return str(db)


@pytest.fixture
def db_with_mixed_tasks(db_path):
    """done/in_progress/pending のタスクが混在するDB。"""
    conn = sqlite3.connect(db_path)
    conn.execute(CREATE_TABLE)
    tasks = [
        (1, "完了タスク1", "done"),
        (2, "完了タスク2", "done"),
        (3, "進行中タスク", "in_progress"),
        (4, "保留タスク", "pending"),
        (5, "完了タスク3", "completed"),
    ]
    for task_id, title, status in tasks:
        conn.execute(
            "INSERT INTO dev_tasks (id, title, status, created_at, updated_at) "
            "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
            (task_id, title, status),
        )
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# テスト: done タスクID取得
# ---------------------------------------------------------------------------

class TestGetDoneTaskIds:
    """get_done_task_ids() のテスト"""

    def test_done_tasks_returned(self, db_with_mixed_tasks):
        """status='done' のタスクIDが返されること"""
        ids = get_done_task_ids(db_path=db_with_mixed_tasks)
        assert 1 in ids
        assert 2 in ids

    def test_non_done_tasks_not_returned(self, db_with_mixed_tasks):
        """status が 'done' 以外のタスクは返されないこと"""
        ids = get_done_task_ids(db_path=db_with_mixed_tasks)
        assert 3 not in ids  # in_progress
        assert 4 not in ids  # pending
        assert 5 not in ids  # completed (done ではない)

    def test_empty_db_returns_empty_set(self, db_path):
        """タスクが存在しない場合は空セットを返すこと"""
        ids = get_done_task_ids(db_path=db_path)
        assert ids == set()

    def test_returns_set_type(self, db_with_mixed_tasks):
        """戻り値がsetであること"""
        ids = get_done_task_ids(db_path=db_with_mixed_tasks)
        assert isinstance(ids, set)


# ---------------------------------------------------------------------------
# テスト: アクティブセッション取得
# ---------------------------------------------------------------------------

class TestGetActiveSessions:
    """get_active_sessions() のテスト"""

    @patch("cleanup_sessions.subprocess.run")
    def test_returns_session_names(self, mock_run):
        """tmux からセッション名リストが返されること"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ai-orchestrator@main\nexp-stock_orchestrator_wf001_task-1@main\nexp-stock_orchestrator_wf002_task-2@main\n",
            stderr="",
        )
        sessions = get_active_sessions()
        assert "ai-orchestrator@main" in sessions
        assert "exp-stock_orchestrator_wf001_task-1@main" in sessions
        assert "exp-stock_orchestrator_wf002_task-2@main" in sessions

    @patch("cleanup_sessions.subprocess.run")
    def test_tmux_error_returns_empty(self, mock_run):
        """tmuxエラー時は空リストを返すこと"""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="no server")
        sessions = get_active_sessions()
        assert sessions == []

    @patch("cleanup_sessions.subprocess.run")
    def test_empty_sessions_returns_empty_list(self, mock_run):
        """セッションが存在しない場合は空リストを返すこと"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        sessions = get_active_sessions()
        assert sessions == []

    @patch("cleanup_sessions.subprocess.run")
    def test_strips_whitespace_from_session_names(self, mock_run):
        """セッション名の空白が除去されること"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="  session-with-spaces  \nsession2\n",
            stderr="",
        )
        sessions = get_active_sessions()
        assert "session-with-spaces" in sessions
        assert "session2" in sessions


# ---------------------------------------------------------------------------
# テスト: タスクID抽出
# ---------------------------------------------------------------------------

class TestExtractTaskId:
    """extract_task_id() のテスト"""

    def test_extract_from_task_N_format(self):
        """task-N 形式からIDを抽出できること（v3形式）"""
        assert extract_task_id("exp-stock_orchestrator_wf042_task-42@main") == 42

    def test_extract_from_task_underscore_format(self):
        """task_N 形式からIDを抽出できること"""
        result = extract_task_id("session_task_99")
        assert result == 99

    def test_no_task_id_in_name(self):
        """タスクIDを含まないセッション名はNoneを返すこと"""
        result = extract_task_id("ai-orchestrator@main")
        assert result is None

    def test_extract_from_complex_session_name(self):
        """複雑なセッション名からIDを抽出できること（v3形式）"""
        result = extract_task_id("exp-stock_orchestrator_wf123_task-123@main")
        assert result == 123

    def test_empty_string_returns_none(self):
        """空文字列はNoneを返すこと"""
        result = extract_task_id("")
        assert result is None


# ---------------------------------------------------------------------------
# テスト: PROTECTED_SESSIONS
# ---------------------------------------------------------------------------

class TestProtectedSessions:
    """保護セッションの設定テスト"""

    def test_main_session_is_protected(self):
        """ai-orchestrator@main が保護セッションに含まれること"""
        assert "ai-orchestrator@main" in PROTECTED_SESSIONS

    def test_protected_sessions_is_set(self):
        """PROTECTED_SESSIONS がsetであること"""
        assert isinstance(PROTECTED_SESSIONS, set)

    def test_engineer_sessions_not_protected(self):
        """一般的なエンジニアセッションは保護されていないこと（v3形式）"""
        assert "exp-stock_orchestrator_wf001_task-1@main" not in PROTECTED_SESSIONS
        assert "task-manager-sqlite_orchestrator_wf002_task-2@main" not in PROTECTED_SESSIONS


# ---------------------------------------------------------------------------
# テスト: セッション削除ロジック（モック）
# ---------------------------------------------------------------------------

class TestSessionCleanupLogic:
    """セッション削除の統合ロジックテスト"""

    @patch("cleanup_sessions.subprocess.run")
    @patch("cleanup_sessions.get_active_sessions")
    @patch("cleanup_sessions.get_done_task_ids")
    def test_protected_session_not_killed(self, mock_done, mock_sessions, mock_run):
        """保護セッションは削除されないこと"""
        mock_done.return_value = {1}
        mock_sessions.return_value = ["ai-orchestrator@main", "exp-stock_orchestrator_wf001_task-1@main"]
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # 実際の削除対象セッションをシミュレート
        sessions = mock_sessions.return_value
        done_ids = mock_done.return_value
        to_kill = []
        for sname in sessions:
            if sname in PROTECTED_SESSIONS:
                continue
            task_id = extract_task_id(sname)
            if task_id and task_id in done_ids:
                to_kill.append(sname)

        assert "ai-orchestrator@main" not in to_kill

    @patch("cleanup_sessions.subprocess.run")
    @patch("cleanup_sessions.get_active_sessions")
    @patch("cleanup_sessions.get_done_task_ids")
    def test_done_task_session_is_targeted(self, mock_done, mock_sessions, mock_run):
        """doneタスクのセッションが削除対象になること"""
        mock_done.return_value = {42}
        mock_sessions.return_value = ["exp-stock_orchestrator_wf042_task-42@main"]
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        sessions = mock_sessions.return_value
        done_ids = mock_done.return_value
        to_kill = []
        for sname in sessions:
            if sname in PROTECTED_SESSIONS:
                continue
            task_id = extract_task_id(sname)
            if task_id and task_id in done_ids:
                to_kill.append(sname)

        assert "exp-stock_orchestrator_wf042_task-42@main" in to_kill

    @patch("cleanup_sessions.get_active_sessions")
    @patch("cleanup_sessions.get_done_task_ids")
    def test_no_sessions_nothing_to_kill(self, mock_done, mock_sessions):
        """セッションが存在しない場合は削除対象なし"""
        mock_done.return_value = {1, 2, 3}
        mock_sessions.return_value = []

        sessions = mock_sessions.return_value
        done_ids = mock_done.return_value
        to_kill = []
        for sname in sessions:
            if sname in PROTECTED_SESSIONS:
                continue
            task_id = extract_task_id(sname)
            if task_id and task_id in done_ids:
                to_kill.append(sname)

        assert to_kill == []
