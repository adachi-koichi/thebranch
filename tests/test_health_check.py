#!/usr/bin/env python3
"""
tests/test_health_check.py — health_check.py のユニットテスト

対象: scripts/health_check.py
      - load_ports_yaml()
      - check_url()
      - main() ロジック
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# scripts/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import health_check
from health_check import (
    load_ports_yaml,
    check_url,
    PORTS_YAML,
    TIMEOUT_SEC,
)


# ---------------------------------------------------------------------------
# テスト: load_ports_yaml()
# ---------------------------------------------------------------------------

class TestLoadPortsYaml:
    """load_ports_yaml() のテスト"""

    def test_loads_valid_yaml(self, tmp_path):
        """正常な YAML ファイルを読み込めること"""
        yaml_content = """
projects:
  exp-stock:
    streamlit:
      port: 8501
      url: http://localhost:8501
"""
        yaml_file = tmp_path / "ports.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        with patch.object(health_check, "PORTS_YAML", yaml_file):
            data = load_ports_yaml()

        assert "projects" in data
        assert "exp-stock" in data["projects"]

    def test_loads_actual_ports_yaml(self):
        """実際の ports.yaml が読み込めること"""
        if not PORTS_YAML.exists():
            pytest.skip("ports.yaml が見つかりません")

        data = load_ports_yaml()
        assert isinstance(data, dict)

    def test_missing_file_raises(self, tmp_path):
        """存在しないファイルは例外を発生させること"""
        missing = tmp_path / "nonexistent.yaml"
        with patch.object(health_check, "PORTS_YAML", missing):
            with pytest.raises(FileNotFoundError):
                load_ports_yaml()


# ---------------------------------------------------------------------------
# テスト: check_url()
# ---------------------------------------------------------------------------

class TestCheckUrl:
    """check_url() のテスト"""

    @patch("health_check.requests.get")
    def test_200_returns_none(self, mock_get):
        """200 レスポンスは None を返すこと（正常）"""
        mock_get.return_value = MagicMock(status_code=200)

        result = check_url("proj", "svc", "http://localhost:8501")

        assert result is None

    @patch("health_check.requests.get")
    def test_non_200_returns_error_dict(self, mock_get):
        """200 以外のステータスコードはエラーdictを返すこと"""
        mock_get.return_value = MagicMock(status_code=500)

        result = check_url("proj", "svc", "http://localhost:8501")

        assert result is not None
        assert result["project"] == "proj"
        assert result["service"] == "svc"
        assert result["status_code"] == 500
        assert "500" in result["error"]

    @patch("health_check.requests.get")
    def test_connection_error_returns_error_dict(self, mock_get):
        """接続エラーはエラーdictを返すこと"""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Connection refused")

        result = check_url("proj", "svc", "http://localhost:9999")

        assert result is not None
        assert result["status_code"] is None
        assert "ConnectionError" in result["error"]

    @patch("health_check.requests.get")
    def test_timeout_returns_error_dict(self, mock_get):
        """タイムアウトはエラーdictを返すこと"""
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout("Timed out")

        result = check_url("proj", "svc", "http://localhost:8501")

        assert result is not None
        assert result["status_code"] is None
        assert "Timeout" in result["error"]

    @patch("health_check.requests.get")
    def test_error_dict_has_required_fields(self, mock_get):
        """エラーdictに必須フィールドが含まれること"""
        mock_get.return_value = MagicMock(status_code=503)

        result = check_url("my-proj", "my-svc", "http://example.com")

        assert result is not None
        required_fields = {"project", "service", "url", "status_code", "error"}
        assert required_fields.issubset(result.keys())

    @patch("health_check.requests.get")
    def test_general_exception_returns_error_dict(self, mock_get):
        """一般的な例外もエラーdictとして処理されること"""
        mock_get.side_effect = Exception("Unexpected error")

        result = check_url("proj", "svc", "http://localhost:8501")

        assert result is not None
        assert result["status_code"] is None

    @patch("health_check.requests.get")
    def test_redirect_200_returns_none(self, mock_get):
        """リダイレクト後の200はNoneを返すこと"""
        mock_get.return_value = MagicMock(status_code=200)

        result = check_url("proj", "svc", "http://localhost:8501")

        assert result is None
        # allow_redirects=True が渡されていること
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("allow_redirects") is True


# ---------------------------------------------------------------------------
# テスト: main() ロジック（モック使用）
# ---------------------------------------------------------------------------

class TestMainLogic:
    """main() の統合ロジックテスト"""

    @patch("health_check.load_ports_yaml")
    @patch("health_check.check_url")
    def test_main_no_errors_outputs_ok_true(self, mock_check, mock_load, capsys):
        """エラーなしのとき ok=true を出力すること"""
        mock_load.return_value = {
            "projects": {
                "exp-stock": {
                    "streamlit": {
                        "port": 8501,
                        "url": "http://localhost:8501",
                    }
                }
            }
        }
        mock_check.return_value = None  # 正常

        # エラーなし時は SystemExit しない場合もある
        try:
            health_check.main()
        except SystemExit as e:
            assert e.code == 0 or e.code is None

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["ok"] is True
        assert output["errors"] == []

    @patch("health_check.load_ports_yaml")
    @patch("health_check.check_url")
    def test_main_with_errors_outputs_ok_false(self, mock_check, mock_load, capsys):
        """エラーありのとき ok=false を出力すること"""
        mock_load.return_value = {
            "projects": {
                "my-proj": {
                    "api": {
                        "url": "http://localhost:9999",
                    }
                }
            }
        }
        mock_check.return_value = {
            "project": "my-proj",
            "service": "api",
            "url": "http://localhost:9999",
            "status_code": None,
            "error": "ConnectionError",
        }

        with pytest.raises(SystemExit) as exc_info:
            health_check.main()
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["ok"] is False
        assert len(output["errors"]) == 1

    @patch("health_check.load_ports_yaml")
    def test_main_skips_service_without_url(self, mock_load, capsys):
        """urlキーがないサービスはスキップされること"""
        mock_load.return_value = {
            "projects": {
                "my-proj": {
                    "db": {
                        "port": 5432,
                        # url なし
                    }
                }
            }
        }

        try:
            health_check.main()
        except SystemExit as e:
            assert e.code == 0 or e.code is None

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["ok"] is True  # urlなしサービスはスキップ = エラーなし

    @patch("health_check.load_ports_yaml")
    def test_main_handles_empty_projects(self, mock_load, capsys):
        """projects が空の場合も正常動作すること"""
        mock_load.return_value = {"projects": {}}

        try:
            health_check.main()
        except SystemExit as e:
            assert e.code == 0 or e.code is None

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["ok"] is True
        assert output["errors"] == []
