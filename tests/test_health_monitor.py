#!/usr/bin/env python3
"""
tests/test_health_monitor.py — health_check.py のユニットテスト
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import health_check
from health_check import check_url, load_ports_yaml


VALID_YAML = """
projects:
  exp-stock:
    streamlit:
      port: 8501
      url: http://localhost:8501
  THEBRANCH:
    dashboard:
      port: 8503
      url: http://localhost:8503
"""


class TestCheckUrl:
    """check_url() のユニットテスト"""

    def test_check_url_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("health_check.requests.get", return_value=mock_resp):
            result = check_url("exp-stock", "streamlit", "http://localhost:8501")
        assert result is None

    def test_check_url_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("health_check.requests.get", return_value=mock_resp):
            result = check_url("exp-stock", "streamlit", "http://localhost:8501")
        assert result is not None
        assert result["project"] == "exp-stock"
        assert result["service"] == "streamlit"
        assert result["status_code"] == 503
        assert "503" in result["error"]

    def test_check_url_timeout(self):
        import requests as req_lib
        with patch("health_check.requests.get", side_effect=req_lib.exceptions.Timeout):
            result = check_url("exp-stock", "streamlit", "http://localhost:8501")
        assert result is not None
        assert result["status_code"] is None
        assert "Timeout" in result["error"]

    def test_check_url_connection_error(self):
        import requests as req_lib
        with patch("health_check.requests.get", side_effect=req_lib.exceptions.ConnectionError("refused")):
            result = check_url("exp-stock", "streamlit", "http://localhost:8501")
        assert result is not None
        assert result["status_code"] is None
        assert "ConnectionError" in result["error"]

    def test_check_url_result_keys(self):
        import requests as req_lib
        with patch("health_check.requests.get", side_effect=req_lib.exceptions.Timeout):
            result = check_url("proj", "svc", "http://example.com")
        assert "project" in result
        assert "service" in result
        assert "url" in result
        assert "status_code" in result
        assert "error" in result

    def test_check_url_unexpected_exception(self):
        with patch("health_check.requests.get", side_effect=Exception("unexpected")):
            result = check_url("proj", "svc", "http://example.com")
        assert result is not None
        assert "unexpected" in result["error"]


class TestLoadPortsYaml:
    """load_ports_yaml() のユニットテスト"""

    def test_load_ports_yaml_valid(self):
        with patch("health_check.PORTS_YAML") as mock_path:
            mock_path.open.return_value.__enter__ = lambda s: s
            mock_path.open.return_value.__exit__ = MagicMock(return_value=False)
            mock_path.open.return_value.read = MagicMock(return_value=VALID_YAML)
            with patch("builtins.open", mock_open(read_data=VALID_YAML)):
                with patch.object(Path, "open", mock_open(read_data=VALID_YAML)):
                    import yaml
                    data = yaml.safe_load(VALID_YAML)
        assert "projects" in data
        assert "exp-stock" in data["projects"]

    def test_load_ports_yaml_missing(self):
        with patch("health_check.PORTS_YAML") as mock_path:
            mock_path.open.side_effect = FileNotFoundError("not found")
            with pytest.raises(FileNotFoundError):
                load_ports_yaml()

    def test_load_ports_yaml_returns_dict(self, tmp_path):
        yaml_file = tmp_path / "ports.yaml"
        yaml_file.write_text(VALID_YAML, encoding="utf-8")
        with patch("health_check.PORTS_YAML", yaml_file):
            data = load_ports_yaml()
        assert isinstance(data, dict)
        assert "projects" in data


class TestMain:
    """main() の統合テスト"""

    def test_main_all_ok(self, tmp_path, capsys):
        yaml_file = tmp_path / "ports.yaml"
        yaml_file.write_text(VALID_YAML, encoding="utf-8")

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("health_check.PORTS_YAML", yaml_file), \
             patch("health_check.requests.get", return_value=mock_resp):
            health_check.main()

        captured = capsys.readouterr()
        import json
        output = json.loads(captured.out)
        assert output["ok"] is True
        assert output["errors"] == []

    def test_main_with_error(self, tmp_path, capsys):
        yaml_file = tmp_path / "ports.yaml"
        yaml_file.write_text(VALID_YAML, encoding="utf-8")

        import requests as req_lib
        with patch("health_check.PORTS_YAML", yaml_file), \
             patch("health_check.requests.get", side_effect=req_lib.exceptions.ConnectionError("refused")), \
             pytest.raises(SystemExit) as exc:
            health_check.main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        import json
        output = json.loads(captured.out)
        assert output["ok"] is False
        assert len(output["errors"]) > 0

    def test_main_no_url_services_skipped(self, tmp_path, capsys):
        no_url_yaml = """
projects:
  myproject:
    backend:
      port: 9000
"""
        yaml_file = tmp_path / "ports.yaml"
        yaml_file.write_text(no_url_yaml, encoding="utf-8")

        with patch("health_check.PORTS_YAML", yaml_file):
            health_check.main()

        captured = capsys.readouterr()
        import json
        output = json.loads(captured.out)
        assert output["ok"] is True
        assert output["errors"] == []
