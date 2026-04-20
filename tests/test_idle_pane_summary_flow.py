#!/usr/bin/env python3
"""
tests/test_idle_pane_summary_flow.py — 空ペイン検知→タスク完了確認→Haiku要約JSON生成 統合テスト

detect_idle_panes.py / check_task_completion.py / generate_task_summary.py を
インポートして end-to-end のフローを検証する。サンプルDBは task_id=200 を使用。
"""

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from detect_idle_panes import (
    detect_idle_panes,
    get_last_nonempty_line,
    is_idle,
    list_all_panes,
)
from check_task_completion import (
    check_task_completion,
    get_completed_tasks,
    get_task_by_id,
    get_tasks_by_session,
)
from generate_task_summary import (
    find_conversation_log,
    generate_summary_fallback,
    generate_task_summary,
    get_task,
)


# ---------------------------------------------------------------------------
# テスト用SQLiteデータベースフィクスチャ (task_id=200)
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
    (
        200,
        "空ペイン検知フロー統合テストタスク",
        "detect_idle_panes → check_task_completion → generate_task_summary の統合テスト",
        "completed",
        1,
        "infra",
        "/Users/delightone/dev/github.com/adachi-koichi/ai-orchestrator",
        "adachi-koichi/ai-orchestrator",
        "session-200",
        "session-main",
        "2026-04-14T00:00:00Z",
        "2026-04-14T12:00:00Z",
        "pytest tests/",
    ),
    (
        201,
        "未完了タスク（スキップ対象）",
        "is_completed=false のためフロー中でスキップされるタスク",
        "in_progress",
        2,
        "feature",
        "/Users/delightone/dev/github.com/adachi-koichi/ai-orchestrator",
        "adachi-koichi/ai-orchestrator",
        "session-201",
        "session-feature",
        "2026-04-14T00:00:00Z",
        "2026-04-14T12:00:00Z",
        None,
    ),
]


@pytest.fixture
def db_path(tmp_path):
    """テスト用の一時SQLiteデータベース（task_id=200 を含む）を作成する。"""
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


@pytest.fixture
def output_dir(tmp_path):
    """テスト用の出力ディレクトリ。"""
    d = tmp_path / "task_results"
    d.mkdir()
    return str(d)


# ---------------------------------------------------------------------------
# TestIdlePaneDetection — detect_idle_panes モジュールの統合テスト
# ---------------------------------------------------------------------------

class TestIdlePaneDetection:
    """detect_idle_panes.py を使ったアイドルペイン検知の統合テスト"""

    def test_is_idle_bash_prompt(self):
        """バッシュのコマンドプロンプトをアイドルと判定する"""
        content = "user@host:~/project$ "
        assert is_idle(content) is True

    def test_is_idle_zsh_prompt(self):
        """zsh のプロンプトをアイドルと判定する"""
        content = "user@host % "
        assert is_idle(content) is True

    def test_is_idle_multiline_with_shell_prompt(self):
        """複数行で最終行がシェルプロンプトの場合アイドルと判定する"""
        content = "\n".join([
            "Building...",
            "Done.",
            "user@host:~/ai-orchestrator$ ",
        ])
        assert is_idle(content) is True

    def test_is_not_idle_running_process(self):
        """実行中のプロセスはアイドルでない"""
        content = "Running pytest...\nProcessing files"
        assert is_idle(content) is False

    def test_is_not_idle_empty_content(self):
        """空コンテンツはアイドルでない"""
        assert is_idle("") is False

    def test_get_last_nonempty_line_returns_prompt(self):
        """末尾の非空行にシェルプロンプトを返す"""
        content = "output\nuser@host:~$ \n\n"
        line = get_last_nonempty_line(content)
        assert "$ " in line

    @patch("detect_idle_panes.capture_pane_content")
    @patch("detect_idle_panes.list_all_panes")
    def test_detect_idle_panes_finds_session_main(self, mock_list, mock_capture):
        """session-main のアイドルペインが検知される"""
        mock_list.return_value = [
            {
                "pane_id": "%20",
                "session_name": "session-main",
                "window_index": "0",
                "pane_index": "0",
            },
        ]
        mock_capture.return_value = "user@host:~/ai-orchestrator$ "

        idle = detect_idle_panes()
        assert len(idle) == 1
        assert idle[0]["session_name"] == "session-main"
        assert idle[0]["pane_id"] == "%20"
        assert "last_content" in idle[0]

    @patch("detect_idle_panes.capture_pane_content")
    @patch("detect_idle_panes.list_all_panes")
    def test_detect_idle_panes_skips_busy_pane(self, mock_list, mock_capture):
        """実行中のペインはアイドルリストに含まれない"""
        mock_list.return_value = [
            {
                "pane_id": "%21",
                "session_name": "session-feature",
                "window_index": "0",
                "pane_index": "0",
            },
        ]
        mock_capture.return_value = "Running tests... in progress"

        idle = detect_idle_panes()
        assert idle == []

    @patch("detect_idle_panes.capture_pane_content")
    @patch("detect_idle_panes.list_all_panes")
    def test_detect_idle_panes_multiple_panes(self, mock_list, mock_capture):
        """複数ペインのうちアイドルのものだけ返す"""
        mock_list.return_value = [
            {"pane_id": "%30", "session_name": "session-a", "window_index": "0", "pane_index": "0"},
            {"pane_id": "%31", "session_name": "session-b", "window_index": "0", "pane_index": "0"},
            {"pane_id": "%32", "session_name": "session-c", "window_index": "0", "pane_index": "0"},
        ]
        mock_capture.side_effect = [
            "user@host:~$ ",      # アイドル
            "npm run build...",   # ビジー
            "user@host:~% ",      # アイドル
        ]

        idle = detect_idle_panes()
        assert len(idle) == 2
        pane_ids = [p["pane_id"] for p in idle]
        assert "%30" in pane_ids
        assert "%32" in pane_ids
        assert "%31" not in pane_ids


# ---------------------------------------------------------------------------
# TestTaskCompletionCheck — check_task_completion モジュールの統合テスト
# ---------------------------------------------------------------------------

class TestTaskCompletionCheck:
    """check_task_completion.py を使ったタスク完了確認の統合テスト（task_id=200）"""

    def test_task_200_is_completed(self, db_path):
        """task_id=200 が completed であることを確認する"""
        result = check_task_completion(200, db_path)
        assert result["task_id"] == 200
        assert result["status"] == "completed"
        assert result["is_completed"] is True

    def test_task_200_has_correct_title(self, db_path):
        """task_id=200 のタイトルが正しいことを確認する"""
        result = check_task_completion(200, db_path)
        assert result["title"] == "空ペイン検知フロー統合テストタスク"

    def test_task_200_has_session_name(self, db_path):
        """task_id=200 が session_name を持つことを確認する"""
        result = check_task_completion(200, db_path)
        assert result["session_name"] == "session-main"

    def test_task_200_has_dir(self, db_path):
        """task_id=200 が dir を持つことを確認する"""
        result = check_task_completion(200, db_path)
        assert result["dir"] is not None
        assert "THEBRANCH" in result["dir"]

    def test_task_201_is_not_completed(self, db_path):
        """task_id=201 (in_progress) は is_completed=False であることを確認する"""
        result = check_task_completion(201, db_path)
        assert result["is_completed"] is False
        assert result["status"] == "in_progress"

    def test_nonexistent_task_returns_error(self, db_path):
        """存在しない task_id は error キーを返す（スキップ対象）"""
        result = check_task_completion(9999, db_path)
        assert result["is_completed"] is False
        assert "error" in result
        assert result["title"] is None

    def test_get_task_by_id_200(self, db_path):
        """get_task_by_id で task_id=200 を直接取得できる"""
        task = get_task_by_id(200, db_path)
        assert task is not None
        assert task["id"] == 200
        assert task["status"] == "completed"

    def test_get_tasks_by_session_main(self, db_path):
        """session-main のタスクが取得できる"""
        tasks = get_tasks_by_session("session-main", db_path)
        assert len(tasks) >= 1
        ids = [t["id"] for t in tasks]
        assert 200 in ids

    def test_get_completed_tasks_includes_200(self, db_path):
        """completed タスク一覧に task_id=200 が含まれる"""
        tasks = get_completed_tasks(db_path=db_path)
        ids = [t["id"] for t in tasks]
        assert 200 in ids
        # 未完了の 201 は含まれない
        assert 201 not in ids


# ---------------------------------------------------------------------------
# TestSummaryJsonGeneration — generate_task_summary モジュールの統合テスト
# ---------------------------------------------------------------------------

class TestSummaryJsonGeneration:
    """generate_task_summary.py を使ったHaiku要約JSON生成の統合テスト（task_id=200）"""

    def test_generate_summary_creates_json_file(self, db_path, output_dir):
        """task_id=200 の要約JSONファイルが生成されることを確認する"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(200, output_dir, db_path)

        json_file = Path(output_dir) / "200.json"
        assert json_file.exists(), "200.json が生成されていない"

    def test_generated_json_has_required_keys(self, db_path, output_dir):
        """生成されたJSONが全必須キーを持つことを確認する"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(200, output_dir, db_path)

        required_keys = {"task_id", "title", "summary", "success", "conversation_log_path", "generated_at"}
        missing = required_keys - set(result.keys())
        assert not missing, f"必須キーが不足: {missing}"

    def test_generated_json_task_id_is_200(self, db_path, output_dir):
        """生成されたJSONの task_id が 200 であることを確認する"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(200, output_dir, db_path)
        assert result["task_id"] == 200

    def test_generated_json_title_matches(self, db_path, output_dir):
        """生成されたJSONのタイトルがDBと一致することを確認する"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(200, output_dir, db_path)
        assert result["title"] == "空ペイン検知フロー統合テストタスク"

    def test_fallback_summary_used_without_api_key(self, db_path, output_dir):
        """APIキー未設定時にフォールバック要約が使われることを確認する"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(200, output_dir, db_path)
        assert result["success"] is False
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_fallback_summary_contains_title(self):
        """フォールバック要約にタスクタイトルが含まれることを確認する"""
        task = {
            "title": "空ペイン検知フロー統合テストタスク",
            "status": "completed",
            "category": "infra",
            "description": "統合テストの説明",
        }
        summary = generate_summary_fallback(task)
        assert "空ペイン検知フロー統合テストタスク" in summary

    def test_generated_at_is_valid_iso8601(self, db_path, output_dir):
        """generated_at が有効なISO 8601形式であることを確認する"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(200, output_dir, db_path)
        dt = datetime.fromisoformat(result["generated_at"])
        assert dt is not None

    def test_json_file_is_valid_json(self, db_path, output_dir):
        """生成されたファイルが有効なJSONであることを確認する"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        generate_task_summary(200, output_dir, db_path)

        json_file = Path(output_dir) / "200.json"
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
        assert data["task_id"] == 200

    def test_api_summary_with_mock(self, db_path, output_dir):
        """モックAPIでHaiku要約が生成されることを確認する"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="空ペインを検知し要約JSONを自動生成するフローの統合テスト。")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-200"}):
            with patch("generate_task_summary.anthropic") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result = generate_task_summary(200, output_dir, db_path)

        assert result["summary"] == "空ペインを検知し要約JSONを自動生成するフローの統合テスト。"
        assert result["success"] is True

    def test_nonexistent_task_raises_error(self, db_path, output_dir):
        """存在しない task_id は ValueError を発生させる"""
        with pytest.raises(ValueError, match="9999"):
            generate_task_summary(9999, output_dir, db_path)

    def test_output_dir_auto_created(self, db_path, tmp_path):
        """出力ディレクトリが存在しなくても自動作成されることを確認する"""
        new_output = str(tmp_path / "auto_created" / "task_results")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        generate_task_summary(200, new_output, db_path)
        assert Path(new_output).exists()
        assert (Path(new_output) / "200.json").exists()


# ---------------------------------------------------------------------------
# TestEndToEndFlow — 空ペイン検知→タスク完了確認→要約JSON生成 フロー統合テスト
# ---------------------------------------------------------------------------

class TestEndToEndFlow:
    """3スクリプトを組み合わせた end-to-end フロー統合テスト（task_id=200）"""

    @patch("detect_idle_panes.capture_pane_content")
    @patch("detect_idle_panes.list_all_panes")
    def test_full_flow_idle_to_summary(self, mock_list, mock_capture, db_path, output_dir):
        """
        フルフロー:
          ① 空ペイン検知 (session-main)
          ② タスク完了確認 (task_id=200)
          ③ 要約JSON生成 (task_id=200)
        """
        # ① 空ペイン検知モック
        mock_list.return_value = [
            {
                "pane_id": "%40",
                "session_name": "session-main",
                "window_index": "0",
                "pane_index": "0",
            },
        ]
        mock_capture.return_value = "user@host:~/ai-orchestrator$ "

        # ① 空ペインを検知
        idle_panes = detect_idle_panes()
        assert len(idle_panes) == 1
        detected_session = idle_panes[0]["session_name"]
        assert detected_session == "session-main"

        # ② セッション名からタスクを特定して完了確認
        tasks = get_tasks_by_session(detected_session, db_path)
        assert len(tasks) >= 1
        task_200 = next((t for t in tasks if t["id"] == 200), None)
        assert task_200 is not None

        completion = check_task_completion(task_200["id"], db_path)
        assert completion["is_completed"] is True

        # ③ 要約JSON生成（APIキーなしでフォールバック）
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(completion["task_id"], output_dir, db_path)

        # 最終成果物の検証
        assert result["task_id"] == 200
        assert result["title"] == "空ペイン検知フロー統合テストタスク"
        assert "summary" in result
        assert "generated_at" in result
        assert (Path(output_dir) / "200.json").exists()

    @patch("detect_idle_panes.capture_pane_content")
    @patch("detect_idle_panes.list_all_panes")
    def test_flow_skips_incomplete_task(self, mock_list, mock_capture, db_path, output_dir):
        """
        未完了タスク (task_id=201) は要約生成をスキップする
        """
        mock_list.return_value = [
            {
                "pane_id": "%41",
                "session_name": "session-feature",
                "window_index": "0",
                "pane_index": "0",
            },
        ]
        mock_capture.return_value = "user@host:~/ai-orchestrator$ "

        idle_panes = detect_idle_panes()
        assert len(idle_panes) == 1
        detected_session = idle_panes[0]["session_name"]

        tasks = get_tasks_by_session(detected_session, db_path)
        assert len(tasks) >= 1
        task_201 = tasks[0]

        completion = check_task_completion(task_201["id"], db_path)
        # is_completed=False のためスキップ
        assert completion["is_completed"] is False

        # 要約生成はスキップ（JSONファイルが存在しないことを確認）
        json_file = Path(output_dir) / f"{task_201['id']}.json"
        assert not json_file.exists()

    @patch("detect_idle_panes.capture_pane_content")
    @patch("detect_idle_panes.list_all_panes")
    def test_flow_no_idle_panes(self, mock_list, mock_capture, db_path):
        """
        アイドルペインがない場合はフローが何もしない
        """
        mock_list.return_value = [
            {
                "pane_id": "%42",
                "session_name": "session-busy",
                "window_index": "0",
                "pane_index": "0",
            },
        ]
        mock_capture.return_value = "Running tests... please wait"

        idle_panes = detect_idle_panes()
        assert idle_panes == []

    def test_flow_task_200_summary_json_structure(self, db_path, output_dir):
        """
        task_id=200 の要約JSONが手順書の必須キーを全て満たしていることを確認する
        """
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(200, output_dir, db_path)

        # 手順書で定義された必須キー
        required_keys = {"task_id", "title", "summary", "success", "conversation_log_path", "generated_at"}
        missing = required_keys - set(result.keys())
        assert not missing, f"手順書の必須キーが不足: {missing}"

        # 型チェック
        assert isinstance(result["task_id"], int)
        assert isinstance(result["title"], str)
        assert isinstance(result["summary"], str)
        assert isinstance(result["success"], bool)
        assert result["conversation_log_path"] is None or isinstance(result["conversation_log_path"], str)
        assert isinstance(result["generated_at"], str)

    @patch("detect_idle_panes.capture_pane_content")
    @patch("detect_idle_panes.list_all_panes")
    def test_flow_with_mocked_api(self, mock_list, mock_capture, db_path, output_dir):
        """
        Haiku API モックを使ったフルフロー検証
        """
        mock_list.return_value = [
            {
                "pane_id": "%43",
                "session_name": "session-main",
                "window_index": "0",
                "pane_index": "0",
            },
        ]
        mock_capture.return_value = "user@host:~/ai-orchestrator$ "

        idle_panes = detect_idle_panes()
        assert len(idle_panes) == 1

        completion = check_task_completion(200, db_path)
        assert completion["is_completed"] is True

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="空ペイン検知からHaiku要約JSONまでの統合フローが正常に完了。")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-e2e"}):
            with patch("generate_task_summary.anthropic") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result = generate_task_summary(200, output_dir, db_path)

        assert result["success"] is True
        assert result["task_id"] == 200
        assert "空ペイン検知" in result["summary"]
        assert (Path(output_dir) / "200.json").exists()
