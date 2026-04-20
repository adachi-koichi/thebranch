#!/usr/bin/env python3
"""
tests/test_stuck_task_detector.py — stuck_task_detector.py のユニットテスト

対象: scripts/stuck_task_detector.py
      - detect_stuck_tasks()
      - _load_discord_token()
      - _load_alerted_ids() / _save_alerted_ids()
      - _extract_project()
      - send_discord_alert()
"""

import datetime
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import stuck_task_detector
from stuck_task_detector import (
    detect_stuck_tasks,
    _load_alerted_ids,
    _save_alerted_ids,
    _extract_project,
    send_discord_alert,
    STUCK_THRESHOLD_HOURS,
    DB_PATH,
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


def make_db(tmp_path: Path) -> str:
    db = tmp_path / "test_tasks.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(CREATE_TABLE)
    conn.commit()
    conn.close()
    return str(db)


def insert_task(db_path: str, task_id: int, title: str, status: str, updated_hours_ago: float, project: str = "test-proj"):
    """テスト用タスクを挿入する。"""
    dt = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(hours=updated_hours_ago)
    ).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO dev_tasks "
        "(id, title, status, dir, project, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (task_id, title, status, f"/dev/github.com/adachi-koichi/{project}", project, dt, dt),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# テスト: detect_stuck_tasks()
# ---------------------------------------------------------------------------

class TestDetectStuckTasks:
    """detect_stuck_tasks() のテスト"""

    def test_stuck_task_detected(self, tmp_path):
        """2時間以上 in_progress のタスクが検知されること"""
        db_path = make_db(tmp_path)
        insert_task(db_path, 1, "スタックタスク", "in_progress", updated_hours_ago=3)

        stuck = detect_stuck_tasks(db_path=db_path, threshold_hours=2)

        ids = [t["id"] for t in stuck]
        assert 1 in ids

    def test_recent_inprogress_not_detected(self, tmp_path):
        """30分前から in_progress のタスクは検知されないこと（閾値2時間）"""
        db_path = make_db(tmp_path)
        insert_task(db_path, 2, "最近のタスク", "in_progress", updated_hours_ago=0.5)

        stuck = detect_stuck_tasks(db_path=db_path, threshold_hours=2)

        ids = [t["id"] for t in stuck]
        assert 2 not in ids

    def test_non_inprogress_not_detected(self, tmp_path):
        """in_progress 以外のステータスのタスクは検知されないこと"""
        db_path = make_db(tmp_path)
        insert_task(db_path, 3, "pendingタスク", "pending", updated_hours_ago=5)
        insert_task(db_path, 4, "completedタスク", "completed", updated_hours_ago=5)

        stuck = detect_stuck_tasks(db_path=db_path, threshold_hours=2)

        ids = [t["id"] for t in stuck]
        assert 3 not in ids
        assert 4 not in ids

    def test_stuck_task_has_required_fields(self, tmp_path):
        """スタックタスクdictに必須フィールドが含まれること"""
        db_path = make_db(tmp_path)
        insert_task(db_path, 10, "スタックタスク", "in_progress", updated_hours_ago=3)

        stuck = detect_stuck_tasks(db_path=db_path, threshold_hours=2)

        assert len(stuck) >= 1
        task = stuck[0]
        assert "id" in task
        assert "title" in task
        assert "elapsed_hours" in task
        assert "project" in task

    def test_elapsed_hours_is_correct(self, tmp_path):
        """elapsed_hours が正しく計算されること"""
        db_path = make_db(tmp_path)
        insert_task(db_path, 5, "スタックタスク", "in_progress", updated_hours_ago=4)

        stuck = detect_stuck_tasks(db_path=db_path, threshold_hours=2)

        matching = [t for t in stuck if t["id"] == 5]
        assert len(matching) == 1
        # 4時間前 → elapsed_hours ≈ 4.0 (誤差1時間以内)
        assert abs(matching[0]["elapsed_hours"] - 4.0) < 1.0

    def test_empty_db_returns_empty(self, tmp_path):
        """タスクがない場合は空リストを返すこと"""
        db_path = make_db(tmp_path)
        stuck = detect_stuck_tasks(db_path=db_path, threshold_hours=2)
        assert stuck == []

    def test_nonexistent_db_returns_empty(self, tmp_path):
        """存在しないDBは空リストを返すこと（例外なし）"""
        stuck = detect_stuck_tasks(
            db_path=str(tmp_path / "nonexistent.sqlite"), threshold_hours=2
        )
        assert stuck == []

    def test_custom_threshold_hours(self, tmp_path):
        """カスタム閾値時間が正しく適用されること"""
        db_path = make_db(tmp_path)
        insert_task(db_path, 6, "タスク", "in_progress", updated_hours_ago=1.5)

        # 閾値2時間 → 検知されない
        stuck_2h = detect_stuck_tasks(db_path=db_path, threshold_hours=2)
        assert 6 not in [t["id"] for t in stuck_2h]

        # 閾値1時間 → 検知される
        stuck_1h = detect_stuck_tasks(db_path=db_path, threshold_hours=1)
        assert 6 in [t["id"] for t in stuck_1h]


# ---------------------------------------------------------------------------
# テスト: _load_alerted_ids() / _save_alerted_ids()
# ---------------------------------------------------------------------------

class TestAlertedIds:
    """アラート済みIDの保存・読み込みテスト"""

    def test_save_and_load_ids(self, tmp_path):
        """保存したIDが正しく読み込めること"""
        flag_file = str(tmp_path / "alerted.json")
        ids_to_save = {"1", "2", "3"}

        with patch.object(stuck_task_detector, "ALERTED_FLAG_FILE", flag_file):
            _save_alerted_ids(ids_to_save)
            loaded = _load_alerted_ids()

        assert loaded == ids_to_save

    def test_load_nonexistent_file_returns_empty_set(self, tmp_path):
        """存在しないフラグファイルは空セットを返すこと"""
        flag_file = str(tmp_path / "nonexistent.json")
        with patch.object(stuck_task_detector, "ALERTED_FLAG_FILE", flag_file):
            ids = _load_alerted_ids()
        assert ids == set()

    def test_save_empty_set(self, tmp_path):
        """空セットを保存して正しく読み込めること"""
        flag_file = str(tmp_path / "alerted.json")
        with patch.object(stuck_task_detector, "ALERTED_FLAG_FILE", flag_file):
            _save_alerted_ids(set())
            loaded = _load_alerted_ids()
        assert loaded == set()


# ---------------------------------------------------------------------------
# テスト: _extract_project()
# ---------------------------------------------------------------------------

class TestExtractProject:
    """_extract_project() のテスト"""

    def test_extracts_project_from_path(self):
        """adachi-koichi 以下のディレクトリ名が返されること"""
        result = _extract_project("/Users/delightone/dev/github.com/adachi-koichi/exp-stock")
        assert result == "exp-stock"

    def test_returns_last_component_when_no_adachi(self):
        """adachi-koichi がないパスは最後のコンポーネントを返すこと"""
        result = _extract_project("/tmp/some-project")
        assert result == "some-project"

    def test_empty_string_returns_empty(self):
        """空文字列は空文字列を返すこと"""
        result = _extract_project("")
        assert result == ""

    def test_none_returns_empty(self):
        """None は空文字列を返すこと"""
        result = _extract_project(None)
        assert result == ""


# ---------------------------------------------------------------------------
# テスト: send_discord_alert()
# ---------------------------------------------------------------------------

class TestSendDiscordAlert:
    """send_discord_alert() のテスト（モック使用）"""

    @patch("stuck_task_detector._load_discord_token")
    @patch("stuck_task_detector.urllib.request.urlopen")
    @patch("stuck_task_detector._load_alerted_ids")
    @patch("stuck_task_detector._save_alerted_ids")
    def test_send_success_returns_true(self, mock_save, mock_load_ids, mock_urlopen, mock_token):
        """Discord通知成功時は True を返すこと"""
        mock_token.return_value = "test-bot-token"
        mock_load_ids.return_value = set()
        mock_urlopen.return_value = MagicMock()

        tasks = [{"id": 1, "title": "スタックタスク", "elapsed_hours": 3.0, "project": "test-proj"}]
        result = send_discord_alert(tasks)

        assert result is True

    @patch("stuck_task_detector._load_discord_token")
    @patch("stuck_task_detector._load_alerted_ids")
    @patch("stuck_task_detector._save_alerted_ids")
    def test_no_token_prints_to_stdout(self, mock_save, mock_load_ids, mock_token, capsys):
        """トークンがない場合は標準出力に記録して True を返すこと"""
        mock_token.return_value = None
        mock_load_ids.return_value = set()

        tasks = [{"id": 2, "title": "タスク", "elapsed_hours": 2.5, "project": "proj"}]
        result = send_discord_alert(tasks)

        assert result is True
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    @patch("stuck_task_detector._load_discord_token")
    @patch("stuck_task_detector._load_alerted_ids")
    def test_already_alerted_tasks_skipped(self, mock_load_ids, mock_token):
        """既に通知済みのタスクはスキップされること"""
        mock_token.return_value = "token"
        mock_load_ids.return_value = {"1"}  # ID=1 は既に通知済み

        tasks = [{"id": 1, "title": "スタック", "elapsed_hours": 3.0, "project": "proj"}]

        with patch("stuck_task_detector.urllib.request.urlopen") as mock_urlopen:
            send_discord_alert(tasks)
            # 既に通知済みなので urlopen は呼ばれない
            mock_urlopen.assert_not_called()

    @patch("stuck_task_detector._load_discord_token")
    @patch("stuck_task_detector.urllib.request.urlopen")
    @patch("stuck_task_detector._load_alerted_ids")
    @patch("stuck_task_detector._save_alerted_ids")
    def test_http_error_returns_false(self, mock_save, mock_load_ids, mock_urlopen, mock_token):
        """HTTP送信エラーは False を返すこと"""
        mock_token.return_value = "test-token"
        mock_load_ids.return_value = set()
        mock_urlopen.side_effect = Exception("Network error")

        tasks = [{"id": 3, "title": "タスク", "elapsed_hours": 3.0, "project": "proj"}]
        result = send_discord_alert(tasks)

        assert result is False
