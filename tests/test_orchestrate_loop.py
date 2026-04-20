#!/usr/bin/env python3
"""
tests/test_orchestrate_loop.py — orchestrate_loop.py の動作テストスイート

テスト対象:
  - tmuxペイン一覧取得の正常動作（detect_idle_panesのモック）
  - 長期pendingタスク検知ロジック（check_long_pending_tasks）
  - メッセージ送信後確認ロジック（send_and_confirm）
  - リトライロジック（delegate_task_with_retry）
  - Discord通知機能（build_agent_status_summary, should_send_summary, send_discord_message）
  - run_once() 統合テスト
"""

import datetime
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, call

import pytest

# scripts/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import orchestrate_loop
from orchestrate_loop import (
    check_long_pending_tasks,
    send_and_confirm,
    delegate_task_with_retry,
    build_agent_status_summary,
    should_send_summary,
    update_last_summary_time,
    send_discord_message,
    get_active_agent_sessions,
    get_completed_tasks_last_hour,
    run_once,
    SUMMARY_INTERVAL_SECONDS,
    PROTECTED_SESSIONS,
)


# ---------------------------------------------------------------------------
# フィクスチャ
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


@pytest.fixture
def db_path(tmp_path):
    """テスト用の一時SQLiteデータベースを作成する。"""
    db = tmp_path / "test_tasks.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(CREATE_TABLE)
    conn.commit()
    conn.close()
    return str(db)


@pytest.fixture
def db_with_long_pending(db_path):
    """1時間以上前からpendingのタスクを含むDB。"""
    past = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    ).strftime("%Y-%m-%d %H:%M:%S")
    recent = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
    ).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db_path)
    conn.execute(CREATE_TABLE)
    conn.execute(
        "INSERT INTO dev_tasks (id,title,description,status,priority,category,dir,project,"
        "session_id,session_name,created_at,updated_at,test_cmd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (1, "古いタスク", "2時間前", "pending", 1, "test", "/dir", "proj", "s1", "sess1", past, past, None),
    )
    conn.execute(
        "INSERT INTO dev_tasks (id,title,description,status,priority,category,dir,project,"
        "session_id,session_name,created_at,updated_at,test_cmd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (2, "新しいタスク", "10分前", "pending", 2, "test", "/dir", "proj", "s2", "sess2", recent, recent, None),
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def db_with_completed(db_path):
    """直近1時間に完了したタスクを含むDB。"""
    recent = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30)
    ).strftime("%Y-%m-%d %H:%M:%S")
    old = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
    ).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db_path)
    conn.execute(CREATE_TABLE)
    conn.execute(
        "INSERT INTO dev_tasks (id,title,description,status,priority,category,dir,project,"
        "session_id,session_name,created_at,updated_at,test_cmd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (10, "最近完了", "30分前", "completed", 1, "test", "/dir", "proj", "s1", "s1", recent, recent, None),
    )
    conn.execute(
        "INSERT INTO dev_tasks (id,title,description,status,priority,category,dir,project,"
        "session_id,session_name,created_at,updated_at,test_cmd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (11, "古い完了", "3時間前", "completed", 1, "test", "/dir", "proj", "s2", "s2", old, old, None),
    )
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# テスト: tmuxペイン一覧取得 (detect_idle_panes のモック動作)
# ---------------------------------------------------------------------------

class TestTmuxPaneListing:
    """tmuxペイン一覧取得の正常動作テスト"""

    @patch("orchestrate_loop.detect_idle_panes")
    def test_idle_panes_returned_in_results(self, mock_detect):
        """detect_idle_panes の結果が run_once() に反映されること"""
        pane = {
            "pane_id": "%5",
            "session_name": "exp-stock@v1",
            "window_index": "0",
            "pane_index": "0",
            "last_content": "user@host:~/project$ ",
        }
        mock_detect.return_value = [pane]

        with patch("orchestrate_loop.get_completed_tasks", return_value=[]), \
             patch("orchestrate_loop.should_send_summary", return_value=False):
            results = run_once()

        assert len(results["idle_panes"]) == 1
        assert results["idle_panes"][0]["pane_id"] == "%5"
        assert results["idle_panes"][0]["session_name"] == "exp-stock@v1"

    @patch("orchestrate_loop.detect_idle_panes")
    def test_no_idle_panes_no_crash(self, mock_detect):
        """アイドルペインが0件でもクラッシュしないこと"""
        mock_detect.return_value = []

        with patch("orchestrate_loop.get_completed_tasks", return_value=[]), \
             patch("orchestrate_loop.should_send_summary", return_value=False):
            results = run_once()

        assert results["idle_panes"] == []

    @patch("orchestrate_loop.detect_idle_panes")
    def test_multiple_panes_all_included(self, mock_detect):
        """複数ペインが全て結果に含まれること"""
        panes = [
            {"pane_id": f"%{i}", "session_name": f"session-{i}", "window_index": "0", "pane_index": "0", "last_content": "$ "}
            for i in range(3)
        ]
        mock_detect.return_value = panes

        with patch("orchestrate_loop.get_completed_tasks", return_value=[]), \
             patch("orchestrate_loop.should_send_summary", return_value=False):
            results = run_once()

        assert len(results["idle_panes"]) == 3


# ---------------------------------------------------------------------------
# テスト: 長期pendingタスク検知ロジック
# ---------------------------------------------------------------------------

class TestCheckLongPendingTasks:
    """check_long_pending_tasks() のテスト"""

    def test_long_pending_task_detected(self, db_with_long_pending):
        """2時間前からpendingのタスクが検知されること"""
        alerts = check_long_pending_tasks(
            db_path=db_with_long_pending, threshold_minutes=60
        )

        assert len(alerts) >= 1
        ids = [a["task_id"] for a in alerts]
        assert 1 in ids  # 2時間前のタスク

    def test_recent_pending_task_not_detected(self, db_with_long_pending):
        """10分前のpendingタスクはしきい値未満のため検知されないこと"""
        alerts = check_long_pending_tasks(
            db_path=db_with_long_pending, threshold_minutes=60
        )

        ids = [a["task_id"] for a in alerts]
        assert 2 not in ids  # 10分前のタスクは検知されない

    def test_alert_has_required_fields(self, db_with_long_pending):
        """アラートオブジェクトに必須フィールドが含まれること"""
        alerts = check_long_pending_tasks(
            db_path=db_with_long_pending, threshold_minutes=60
        )

        for alert in alerts:
            assert "ts" in alert
            assert "task_id" in alert
            assert "title" in alert
            assert "pending_minutes" in alert
            assert alert["pending_minutes"] >= 60

    def test_empty_db_returns_empty(self, db_path):
        """pendingタスクがないDBは空リストを返すこと"""
        alerts = check_long_pending_tasks(db_path=db_path, threshold_minutes=60)
        assert alerts == []

    def test_nonexistent_db_returns_empty(self, tmp_path):
        """存在しないDBパスは空リストを返すこと（例外なし）"""
        alerts = check_long_pending_tasks(
            db_path=str(tmp_path / "nonexistent.sqlite"), threshold_minutes=60
        )
        assert alerts == []

    def test_custom_threshold(self, db_with_long_pending):
        """カスタムしきい値（30分）でも動作すること"""
        alerts = check_long_pending_tasks(
            db_path=db_with_long_pending, threshold_minutes=30
        )
        # 2時間前のタスクは30分しきい値でも検知される
        ids = [a["task_id"] for a in alerts]
        assert 1 in ids


# ---------------------------------------------------------------------------
# テスト: メッセージ送信後確認ロジック
# ---------------------------------------------------------------------------

class TestSendAndConfirm:
    """send_and_confirm() のテスト（モック使用）"""

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_send_success_no_error(self, mock_sleep, mock_run):
        """送信成功・ペイン内容にエラーなし → success=True"""
        # send-keys 成功
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),       # send-keys
            MagicMock(returncode=0, stdout="user@host:~$ "),  # capture-pane
        ]

        result = send_and_confirm(pane_id="%0", message="hello", wait_seconds=0)

        assert result["success"] is True
        assert result["error"] is None
        assert result["pane_id"] == "%0"

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_send_failure_returns_error(self, mock_sleep, mock_run):
        """send-keys 失敗 → success=False, error に理由が入ること"""
        mock_run.return_value = MagicMock(returncode=1, stderr="no session")

        result = send_and_confirm(pane_id="%99", message="hello", wait_seconds=0)

        assert result["success"] is False
        assert result["error"] is not None

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_error_keyword_in_pane_content(self, mock_sleep, mock_run):
        """ペイン内容に 'error:' キーワード → error検出"""
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),       # send-keys
            MagicMock(returncode=0, stdout="error: command not found"),  # capture-pane
        ]

        result = send_and_confirm(pane_id="%0", message="bad-cmd", wait_seconds=0)

        assert result["success"] is False
        assert result["error"] is not None

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_exception_during_send(self, mock_sleep, mock_run):
        """send-keys 例外発生 → success=False"""
        mock_run.side_effect = Exception("tmux not found")

        result = send_and_confirm(pane_id="%0", message="hello", wait_seconds=0)

        assert result["success"] is False
        assert result["error"] is not None

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_result_has_content_after(self, mock_sleep, mock_run):
        """content_after フィールドが返ること"""
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=0, stdout="some output\nuser$ "),
        ]

        result = send_and_confirm(pane_id="%0", message="ls", wait_seconds=0)

        assert "content_after" in result
        assert isinstance(result["content_after"], str)


# ---------------------------------------------------------------------------
# テスト: リトライロジック
# ---------------------------------------------------------------------------

class TestDelegateTaskWithRetry:
    """delegate_task_with_retry() のテスト（モック使用）"""

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_success_on_first_attempt(self, mock_sleep, mock_run):
        """1回目で成功すること"""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = delegate_task_with_retry(
            session_name="test-session",
            project_dir="/tmp",
            launch_cmd="ccc",
            task_message="タスクを実行してください",
            max_retries=3,
            retry_interval=0,
        )

        assert result["success"] is True
        assert result["retry_count"] == 0
        assert result["error"] is None

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_success_on_second_attempt(self, mock_sleep, mock_run):
        """1回失敗後、2回目で成功すること"""
        fail = MagicMock(returncode=1, stderr="already exists", stdout="")
        success = MagicMock(returncode=0, stderr="", stdout="")
        mock_run.side_effect = [fail, success, success, success]

        result = delegate_task_with_retry(
            session_name="test-session",
            project_dir="/tmp",
            launch_cmd="ccc",
            task_message="タスクを実行してください",
            max_retries=3,
            retry_interval=0,
        )

        assert result["success"] is True
        assert result["retry_count"] >= 1

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_all_retries_fail(self, mock_sleep, mock_run):
        """全リトライ失敗 → success=False, error に理由が入ること"""
        mock_run.return_value = MagicMock(returncode=1, stderr="failed", stdout="")

        result = delegate_task_with_retry(
            session_name="test-session",
            project_dir="/tmp",
            launch_cmd="ccc",
            task_message="タスクを実行してください",
            max_retries=2,
            retry_interval=0,
        )

        assert result["success"] is False
        assert result["error"] is not None
        assert result["session_name"] == "test-session"

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_retry_count_correct(self, mock_sleep, mock_run):
        """retry_count が実際のリトライ回数を反映すること"""
        mock_run.return_value = MagicMock(returncode=1, stderr="err", stdout="")

        result = delegate_task_with_retry(
            session_name="test-session",
            project_dir="/tmp",
            launch_cmd="ccc",
            task_message="msg",
            max_retries=3,
            retry_interval=0,
        )

        assert result["retry_count"] == 2  # 0-indexed: 最後の試行は attempt=3, retry_count=2

    @patch("orchestrate_loop.subprocess.run")
    @patch("orchestrate_loop.time.sleep")
    def test_exception_raises_treated_as_failure(self, mock_sleep, mock_run):
        """subprocess例外が発生しても failure として扱われること"""
        mock_run.side_effect = Exception("tmux crashed")

        result = delegate_task_with_retry(
            session_name="test-session",
            project_dir="/tmp",
            launch_cmd="ccc",
            task_message="msg",
            max_retries=1,
            retry_interval=0,
        )

        assert result["success"] is False


# ---------------------------------------------------------------------------
# テスト: Discord通知機能
# ---------------------------------------------------------------------------

class TestBuildAgentStatusSummary:
    """build_agent_status_summary() のテスト"""

    @patch("orchestrate_loop.get_active_agent_sessions")
    def test_summary_contains_required_sections(self, mock_sessions):
        """サマリーに必須セクションが含まれること"""
        mock_sessions.return_value = [
            "exp-stock_orchestrator_wf001_task-1@main",
            "exp-stock_orchestrator_wf002_task-2@main",
        ]

        summary = build_agent_status_summary(
            idle_panes=[],
            completed_last_hour=[{"id": 1, "title": "完了タスク", "updated_at": "2026-04-15 10:00:00"}],
            long_pending=[{"task_id": 2, "title": "長期pending", "pending_minutes": 90}],
        )

        assert "オーケストレーター状態サマリー" in summary
        assert "アクティブエージェント" in summary
        assert "直近1時間の完了タスク" in summary
        assert "長期pendingタスク" in summary

    @patch("orchestrate_loop.get_active_agent_sessions")
    def test_summary_shows_agent_count(self, mock_sessions):
        """エージェント数が正しく表示されること"""
        mock_sessions.return_value = [
            "exp-stock_orchestrator_wf001_task-1@main",
            "exp-stock_orchestrator_wf002_task-2@main",
        ]

        summary = build_agent_status_summary(
            idle_panes=[],
            completed_last_hour=[],
            long_pending=[],
        )

        assert "2" in summary  # 2セッション

    @patch("orchestrate_loop.get_active_agent_sessions")
    def test_idle_panes_excluded_protected_sessions(self, mock_sessions):
        """保護セッションのアイドルペインはサマリーに表示されないこと"""
        mock_sessions.return_value = []

        idle_panes = [
            {"pane_id": "%0", "session_name": "ai-orchestrator@main", "last_content": "$ "},
            {"pane_id": "%1", "session_name": "exp-stock_orchestrator_wf001_task-1@main", "last_content": "$ "},
        ]
        summary = build_agent_status_summary(
            idle_panes=idle_panes,
            completed_last_hour=[],
            long_pending=[],
        )

        # 保護セッションは表示されない
        assert "ai-orchestrator@main" not in summary
        # 非保護は表示される
        assert "exp-stock_orchestrator_wf001_task-1@main" in summary

    @patch("orchestrate_loop.get_active_agent_sessions")
    def test_summary_truncates_long_lists(self, mock_sessions):
        """6件以上のアイテムは「... 他N件」に省略されること"""
        mock_sessions.return_value = [f"exp-stock_orchestrator_wf{i:03d}_task-{i}@main" for i in range(10)]

        summary = build_agent_status_summary(
            idle_panes=[],
            completed_last_hour=[{"id": i, "title": f"task{i}", "updated_at": ""} for i in range(10)],
            long_pending=[{"task_id": i, "title": f"pending{i}", "pending_minutes": 120} for i in range(10)],
        )

        assert "他" in summary

    @patch("orchestrate_loop.get_active_agent_sessions")
    def test_empty_inputs_no_crash(self, mock_sessions):
        """全て空入力でもクラッシュしないこと"""
        mock_sessions.return_value = []

        summary = build_agent_status_summary(
            idle_panes=[],
            completed_last_hour=[],
            long_pending=[],
        )

        assert isinstance(summary, str)
        assert len(summary) > 0


class TestShouldSendSummary:
    """should_send_summary() のテスト"""

    def test_no_file_returns_true(self, tmp_path):
        """タイムスタンプファイルがない場合はTrueを返すこと"""
        result = should_send_summary(last_summary_file=str(tmp_path / "nonexistent.txt"))
        assert result is True

    def test_recent_timestamp_returns_false(self, tmp_path):
        """直近のタイムスタンプはFalseを返すこと（まだ1時間経過していない）"""
        ts_file = tmp_path / "last_summary.txt"
        ts_file.write_text(str(time.time()))  # 今の時刻

        result = should_send_summary(last_summary_file=str(ts_file))
        assert result is False

    def test_old_timestamp_returns_true(self, tmp_path):
        """1時間以上前のタイムスタンプはTrueを返すこと"""
        ts_file = tmp_path / "last_summary.txt"
        old_ts = time.time() - SUMMARY_INTERVAL_SECONDS - 10
        ts_file.write_text(str(old_ts))

        result = should_send_summary(last_summary_file=str(ts_file))
        assert result is True

    def test_invalid_file_content_returns_true(self, tmp_path):
        """不正なファイル内容はTrueを返すこと（例外にならない）"""
        ts_file = tmp_path / "last_summary.txt"
        ts_file.write_text("not-a-number")

        result = should_send_summary(last_summary_file=str(ts_file))
        assert result is True


class TestSendDiscordMessage:
    """send_discord_message() のテスト（モック使用）"""

    @patch("orchestrate_loop.load_discord_token")
    @patch("orchestrate_loop.urllib.request.urlopen")
    def test_send_success(self, mock_urlopen, mock_token):
        """トークン取得・HTTP成功 → True を返すこと"""
        mock_token.return_value = "test-bot-token"
        mock_urlopen.return_value = MagicMock()

        result = send_discord_message("テストメッセージ")

        assert result is True
        mock_urlopen.assert_called_once()

    @patch("orchestrate_loop.load_discord_token")
    def test_no_token_returns_false(self, mock_token):
        """トークンが見つからない場合はFalseを返すこと"""
        mock_token.return_value = None

        result = send_discord_message("テストメッセージ")

        assert result is False

    @patch("orchestrate_loop.load_discord_token")
    @patch("orchestrate_loop.urllib.request.urlopen")
    def test_http_error_returns_false(self, mock_urlopen, mock_token):
        """HTTP例外発生 → Falseを返すこと（クラッシュしない）"""
        mock_token.return_value = "test-bot-token"
        mock_urlopen.side_effect = Exception("Network error")

        result = send_discord_message("テストメッセージ")

        assert result is False


class TestGetActiveAgentSessions:
    """get_active_agent_sessions() のテスト"""

    @patch("orchestrate_loop.subprocess.run")
    def test_filters_agent_sessions(self, mock_run):
        """v3形式チームセッションのみ返すこと（旧形式 em@/eng@/test- は除外）"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "ai-orchestrator@main\n"
                "exp-stock_orchestrator_wf001_task-1@main\n"
                "exp-stock_orchestrator_wf002_task-2@main\n"
                "em@exp-stock\n"
                "eng@exp-stock-task1\n"
                "test-42\n"
                "other-session\n"
            ),
        )

        sessions = get_active_agent_sessions()

        assert "exp-stock_orchestrator_wf001_task-1@main" in sessions
        assert "exp-stock_orchestrator_wf002_task-2@main" in sessions
        assert "ai-orchestrator@main" not in sessions
        assert "em@exp-stock" not in sessions
        assert "eng@exp-stock-task1" not in sessions
        assert "test-42" not in sessions
        assert "other-session" not in sessions

    @patch("orchestrate_loop.subprocess.run")
    def test_tmux_error_returns_empty(self, mock_run):
        """tmuxエラー時は空リストを返すこと"""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        sessions = get_active_agent_sessions()

        assert sessions == []

    @patch("orchestrate_loop.subprocess.run")
    def test_exception_returns_empty(self, mock_run):
        """例外発生時は空リストを返すこと"""
        mock_run.side_effect = Exception("tmux not found")

        sessions = get_active_agent_sessions()

        assert sessions == []


class TestGetCompletedTasksLastHour:
    """get_completed_tasks_last_hour() のテスト"""

    def test_recent_completed_returned(self, db_with_completed):
        """直近1時間の完了タスクが返されること"""
        tasks = get_completed_tasks_last_hour(db_path=db_with_completed)

        ids = [t["id"] for t in tasks]
        assert 10 in ids  # 30分前に完了

    def test_old_completed_not_returned(self, db_with_completed):
        """3時間前に完了したタスクは返されないこと"""
        tasks = get_completed_tasks_last_hour(db_path=db_with_completed)

        ids = [t["id"] for t in tasks]
        assert 11 not in ids  # 3時間前に完了

    def test_empty_db_returns_empty(self, db_path):
        """完了タスクがないDBは空リストを返すこと"""
        tasks = get_completed_tasks_last_hour(db_path=db_path)
        assert tasks == []

    def test_nonexistent_db_returns_empty(self, tmp_path):
        """存在しないDBは空リストを返すこと（例外なし）"""
        tasks = get_completed_tasks_last_hour(db_path=str(tmp_path / "nonexistent.sqlite"))
        assert tasks == []


# ---------------------------------------------------------------------------
# テスト: run_once() 統合テスト
# ---------------------------------------------------------------------------

class TestRunOnce:
    """run_once() の統合テスト"""

    @patch("orchestrate_loop.detect_idle_panes")
    @patch("orchestrate_loop.get_completed_tasks")
    @patch("orchestrate_loop.should_send_summary")
    def test_returns_correct_structure(self, mock_summary, mock_completed, mock_idle):
        """run_once() が正しい構造の辞書を返すこと"""
        mock_idle.return_value = []
        mock_completed.return_value = []
        mock_summary.return_value = False

        results = run_once()

        assert isinstance(results, dict)
        assert "idle_panes" in results
        assert "completed_tasks" in results
        assert "closed_sessions" in results
        assert "long_pending_alerts" in results
        assert "discord_summary_sent" in results

    @patch("orchestrate_loop.detect_idle_panes")
    @patch("orchestrate_loop.get_completed_tasks")
    @patch("orchestrate_loop.should_send_summary")
    @patch("orchestrate_loop.send_discord_message")
    @patch("orchestrate_loop.update_last_summary_time")
    @patch("orchestrate_loop.get_completed_tasks_last_hour")
    def test_discord_summary_sent_when_interval_reached(
        self, mock_completed_hour, mock_update, mock_discord, mock_summary, mock_completed, mock_idle
    ):
        """1時間経過後にDiscordサマリーが送信されること"""
        mock_idle.return_value = []
        mock_completed.return_value = []
        mock_summary.return_value = True  # 1時間経過
        mock_discord.return_value = True
        mock_completed_hour.return_value = []

        results = run_once()

        mock_discord.assert_called_once()
        mock_update.assert_called_once()
        assert results["discord_summary_sent"] is True

    @patch("orchestrate_loop.detect_idle_panes")
    @patch("orchestrate_loop.get_completed_tasks")
    @patch("orchestrate_loop.should_send_summary")
    @patch("orchestrate_loop.send_discord_message")
    def test_discord_summary_skipped_when_interval_not_reached(
        self, mock_discord, mock_summary, mock_completed, mock_idle
    ):
        """1時間未経過のときDiscordサマリーを送信しないこと"""
        mock_idle.return_value = []
        mock_completed.return_value = []
        mock_summary.return_value = False  # 1時間未経過

        results = run_once()

        mock_discord.assert_not_called()
        assert results["discord_summary_sent"] is False

    @patch("orchestrate_loop.detect_idle_panes")
    @patch("orchestrate_loop.get_completed_tasks")
    @patch("orchestrate_loop.should_send_summary")
    def test_verbose_mode_no_crash(self, mock_summary, mock_completed, mock_idle):
        """verboseモードでもクラッシュしないこと"""
        mock_idle.return_value = []
        mock_completed.return_value = []
        mock_summary.return_value = False

        results = run_once(verbose=True)

        assert results is not None
