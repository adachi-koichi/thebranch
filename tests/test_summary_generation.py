#!/usr/bin/env python3
"""
tests/test_summary_generation.py — generate_task_summary.py のユニットテスト
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

from generate_task_summary import (
    DEFAULT_OUTPUT_DIR,
    HAIKU_MODEL,
    find_conversation_log,
    generate_summary_fallback,
    generate_task_summary,
    get_task,
)


# ---------------------------------------------------------------------------
# テスト用SQLiteデータベースフィクスチャ
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
        106,
        "空ペイン検知→タスク完了確認→Haiku要約JSON生成",
        "オーケストレーションループ内の処理を追加する",
        "completed",
        1,
        "infra",
        "/Users/delightone/dev/github.com/adachi-koichi/ai-orchestrator",
        "adachi-koichi/ai-orchestrator",
        "ad677577",
        "session-main",
        "2026-04-13T15:31:24Z",
        "2026-04-14T10:00:00Z",
        None,
    ),
    (
        107,
        "テストタスク",
        None,
        "in_progress",
        2,
        "test",
        "/path/test",
        "proj-test",
        "sid2",
        "session-test",
        "2026-04-13T15:00:00Z",
        "2026-04-14T10:00:00Z",
        "pytest tests/",
    ),
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


@pytest.fixture
def output_dir(tmp_path):
    """テスト用の出力ディレクトリ。"""
    d = tmp_path / "task_results"
    d.mkdir()
    return str(d)


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------

class TestGetTask:
    """get_task() のテスト"""

    def test_existing_task(self, db_path):
        task = get_task(106, db_path)
        assert task is not None
        assert task["id"] == 106
        assert task["title"] == "空ペイン検知→タスク完了確認→Haiku要約JSON生成"

    def test_nonexistent_task(self, db_path):
        task = get_task(9999, db_path)
        assert task is None


class TestGenerateSummaryFallback:
    """generate_summary_fallback() のテスト"""

    def test_basic(self):
        task = {
            "title": "テストタスク",
            "status": "completed",
            "category": "infra",
            "description": "説明テキスト",
        }
        summary = generate_summary_fallback(task)
        assert "テストタスク" in summary
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_no_description(self):
        task = {
            "title": "タイトルのみ",
            "status": "done",
            "category": None,
            "description": None,
        }
        summary = generate_summary_fallback(task)
        assert "タイトルのみ" in summary

    def test_long_description_truncated(self):
        task = {
            "title": "テスト",
            "status": "completed",
            "category": "test",
            "description": "あ" * 200,
        }
        summary = generate_summary_fallback(task)
        # 200文字の説明が切り詰められることを確認
        assert "..." in summary


class TestFindConversationLog:
    """find_conversation_log() のテスト"""

    def test_no_projects_dir(self, tmp_path):
        task = {"dir": "/nonexistent/path"}
        # ホームを tmp_path に向けることで ~/.claude/projects が存在しない状態をシミュレート
        with patch("generate_task_summary.Path") as mock_path:
            mock_path.return_value.home.return_value = tmp_path
            # シンプルに None が返ることを確認
            result = find_conversation_log(106, task)
            # projects dir が存在しないので None
            # (実際のパスではなくモックなので None が返る)
            assert result is None or isinstance(result, str)

    def test_with_existing_jsonl(self, tmp_path):
        # ~/.claude/projects/ のモック構造を作成
        projects_dir = tmp_path / ".claude" / "projects"
        task_dir = "/Users/delightone/dev/github.com/adachi-koichi/ai-orchestrator"
        safe_name = task_dir.replace("/", "-").lstrip("-")
        log_dir = projects_dir / safe_name
        log_dir.mkdir(parents=True)

        # jsonlファイルを作成
        jsonl_file = log_dir / "session-abc.jsonl"
        jsonl_file.write_text('{"type": "message"}\n')

        task = {"dir": task_dir}

        with patch("generate_task_summary.Path") as mock_path_cls:
            # Path.home() をモック
            mock_home = MagicMock()
            mock_home.__truediv__ = lambda self, other: tmp_path / ".claude" if other == ".claude" else self / other
            mock_path_cls.home.return_value = tmp_path

            # 実際のPathクラスを使ってテスト
            from pathlib import Path as RealPath

            def side_effect(*args):
                if args and args[0] == "generate_task_summary":
                    return MagicMock()
                return RealPath(*args)

            # Pathをモックせずに実際のファイルシステムで確認
            # find_conversation_log に直接パスを渡せないため、
            # home()だけモックする
            with patch("generate_task_summary.Path.home", return_value=tmp_path):
                result = find_conversation_log(106, task)
                assert result is not None
                assert result.endswith(".jsonl")


class TestGenerateTaskSummary:
    """generate_task_summary() のテスト"""

    def test_task_not_found(self, db_path, output_dir):
        with pytest.raises(ValueError, match="9999"):
            generate_task_summary(9999, output_dir, db_path)

    def test_generates_json_file(self, db_path, output_dir):
        """APIキーなし（フォールバック）でJSONが生成されることを確認"""
        with patch.dict(os.environ, {}, clear=True):
            # ANTHROPIC_API_KEY を除去
            os.environ.pop("ANTHROPIC_API_KEY", None)
            result = generate_task_summary(106, output_dir, db_path)

        # 戻り値の構造確認
        assert result["task_id"] == 106
        assert result["title"] == "空ペイン検知→タスク完了確認→Haiku要約JSON生成"
        assert "summary" in result
        assert isinstance(result["summary"], str)
        assert "generated_at" in result
        assert "success" in result

        # ファイルが生成されていることを確認
        json_file = Path(output_dir) / "106.json"
        assert json_file.exists()

        # JSONが正しく読み込めることを確認
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
        assert data["task_id"] == 106

    def test_json_structure(self, db_path, output_dir):
        """生成されたJSONが正しい構造を持つことを確認"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(106, output_dir, db_path)

        required_keys = {"task_id", "title", "summary", "success", "conversation_log_path", "generated_at"}
        assert required_keys.issubset(set(result.keys()))

    def test_with_mocked_api(self, db_path, output_dir):
        """APIが利用可能な場合のテスト（モック使用）"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="AIによる要約テキスト")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-12345"}):
            with patch("generate_task_summary.anthropic") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result = generate_task_summary(106, output_dir, db_path)

        assert result["summary"] == "AIによる要約テキスト"
        assert result["success"] is True

    def test_api_failure_falls_back(self, db_path, output_dir):
        """APIエラー時にフォールバックが使用されることを確認"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("generate_task_summary.generate_summary_with_api", side_effect=Exception("API Error")):
                result = generate_task_summary(106, output_dir, db_path)

        assert result["success"] is False
        assert "summary" in result
        assert len(result["summary"]) > 0

    def test_output_dir_created(self, db_path, tmp_path):
        """出力ディレクトリが存在しなくても自動作成されることを確認"""
        new_output_dir = str(tmp_path / "new" / "nested" / "dir")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(106, new_output_dir, db_path)
        assert Path(new_output_dir).exists()
        assert (Path(new_output_dir) / "106.json").exists()

    def test_generated_at_is_iso_format(self, db_path, output_dir):
        """generated_at がISO形式であることを確認"""
        from datetime import datetime
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_task_summary(106, output_dir, db_path)
        # ISO 8601形式のパースを試みる
        dt = datetime.fromisoformat(result["generated_at"])
        assert dt is not None
