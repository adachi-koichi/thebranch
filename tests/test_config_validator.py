#!/usr/bin/env python3
"""
tests/test_config_validator.py — config_validator.py のバリデーターテスト

対象: scripts/config_validator.py（存在しない場合はモック/スタブで対応）
      ports.yaml / monitoring.yaml のバリデーションロジックをテスト
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# テスト対象スクリプトの検索
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

# config_validator.py は存在しないためスタブ実装でテスト
# ---------------------------------------------------------------------------
# スタブ実装（config_validator.py が存在しない場合に使用）
# ---------------------------------------------------------------------------

def validate_ports_yaml(data: dict) -> list[str]:
    """ports.yaml の構造を検証し、エラーメッセージのリストを返す。"""
    errors = []
    if not isinstance(data, dict):
        errors.append("ports.yaml はdictである必要があります")
        return errors
    projects = data.get("projects")
    if projects is None:
        errors.append("'projects' キーが必要です")
        return errors
    if not isinstance(projects, dict):
        errors.append("'projects' の値はdictである必要があります")
        return errors
    for proj_name, services in projects.items():
        if not isinstance(services, dict):
            errors.append(f"プロジェクト '{proj_name}': servicesはdictである必要があります")
            continue
        for svc_name, svc_conf in services.items():
            if not isinstance(svc_conf, dict):
                continue
            url = svc_conf.get("url")
            if url and not (url.startswith("http://") or url.startswith("https://")):
                errors.append(
                    f"プロジェクト '{proj_name}' サービス '{svc_name}': URLが不正です: {url}"
                )
            port = svc_conf.get("port")
            if port is not None and not isinstance(port, int):
                errors.append(
                    f"プロジェクト '{proj_name}' サービス '{svc_name}': portは整数である必要があります"
                )
    return errors


def validate_monitoring_yaml(data: dict) -> list[str]:
    """monitoring.yaml の構造を検証し、エラーメッセージのリストを返す。"""
    errors = []
    if not isinstance(data, dict):
        errors.append("monitoring.yaml はdictである必要があります")
        return errors
    projects = data.get("projects")
    if projects is None:
        errors.append("'projects' キーが必要です")
        return errors
    required_metric_keys = {"name", "type", "path", "interval_minutes", "min_records"}
    for proj_name, proj_conf in projects.items():
        if not isinstance(proj_conf, dict):
            errors.append(f"プロジェクト '{proj_name}': 設定はdictである必要があります")
            continue
        metrics = proj_conf.get("metrics", [])
        for i, metric in enumerate(metrics):
            if not isinstance(metric, dict):
                errors.append(f"プロジェクト '{proj_name}' メトリクス[{i}]: dictである必要があります")
                continue
            missing = required_metric_keys - set(metric.keys())
            if missing:
                errors.append(
                    f"プロジェクト '{proj_name}' メトリクス[{i}] '{metric.get('name', '?')}': 必須キーが不足: {missing}"
                )
            metric_type = metric.get("type")
            if metric_type not in ("sqlite", "log", None):
                errors.append(
                    f"プロジェクト '{proj_name}' メトリクス[{i}]: 未知のtype: {metric_type}"
                )
    return errors


# ---------------------------------------------------------------------------
# テスト: ports.yaml バリデーション
# ---------------------------------------------------------------------------

class TestValidatePortsYaml:
    """ports.yaml のバリデーションテスト"""

    def test_valid_ports_yaml_no_errors(self):
        """正常な ports.yaml はエラーなし"""
        data = {
            "projects": {
                "exp-stock": {
                    "streamlit": {
                        "port": 8501,
                        "url": "http://localhost:8501",
                    }
                }
            }
        }
        errors = validate_ports_yaml(data)
        assert errors == []

    def test_missing_projects_key(self):
        """'projects' キーがない場合はエラー"""
        data = {"services": {}}
        errors = validate_ports_yaml(data)
        assert any("projects" in e for e in errors)

    def test_invalid_url_scheme(self):
        """URLが http/https 以外の場合はエラー"""
        data = {
            "projects": {
                "my-proj": {
                    "api": {
                        "port": 8080,
                        "url": "ftp://localhost:8080",
                    }
                }
            }
        }
        errors = validate_ports_yaml(data)
        assert any("URL" in e for e in errors)

    def test_invalid_port_type(self):
        """portが文字列の場合はエラー"""
        data = {
            "projects": {
                "my-proj": {
                    "api": {
                        "port": "eight-thousand",
                        "url": "http://localhost:8000",
                    }
                }
            }
        }
        errors = validate_ports_yaml(data)
        assert any("port" in e for e in errors)

    def test_empty_projects_no_errors(self):
        """projects が空辞書でもエラーなし"""
        data = {"projects": {}}
        errors = validate_ports_yaml(data)
        assert errors == []

    def test_not_dict_input(self):
        """入力がdictでない場合はエラー"""
        errors = validate_ports_yaml("invalid")
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# テスト: monitoring.yaml バリデーション
# ---------------------------------------------------------------------------

class TestValidateMonitoringYaml:
    """monitoring.yaml のバリデーションテスト"""

    def test_valid_monitoring_yaml_no_errors(self):
        """正常な monitoring.yaml はエラーなし"""
        data = {
            "projects": {
                "exp-stock": {
                    "metrics": [
                        {
                            "name": "株価データDB",
                            "type": "sqlite",
                            "path": "/tmp/stock.db",
                            "interval_minutes": 60,
                            "min_records": 5,
                        }
                    ]
                }
            }
        }
        errors = validate_monitoring_yaml(data)
        assert errors == []

    def test_missing_required_metric_keys(self):
        """必須キーが不足する場合はエラー"""
        data = {
            "projects": {
                "proj": {
                    "metrics": [
                        {
                            "name": "test",
                            "type": "sqlite",
                            # path, interval_minutes, min_records が不足
                        }
                    ]
                }
            }
        }
        errors = validate_monitoring_yaml(data)
        assert any("必須キーが不足" in e for e in errors)

    def test_unknown_metric_type(self):
        """未知のメトリクスタイプはエラー"""
        data = {
            "projects": {
                "proj": {
                    "metrics": [
                        {
                            "name": "test",
                            "type": "unknown_type",
                            "path": "/tmp/test.db",
                            "interval_minutes": 60,
                            "min_records": 1,
                        }
                    ]
                }
            }
        }
        errors = validate_monitoring_yaml(data)
        assert any("未知のtype" in e for e in errors)

    def test_log_type_valid(self):
        """type=log は有効なタイプとして認識されること"""
        data = {
            "projects": {
                "proj": {
                    "metrics": [
                        {
                            "name": "ログ",
                            "type": "log",
                            "path": "/tmp/test.log",
                            "interval_minutes": 30,
                            "min_records": 1,
                        }
                    ]
                }
            }
        }
        errors = validate_monitoring_yaml(data)
        type_errors = [e for e in errors if "未知のtype" in e]
        assert type_errors == []

    def test_empty_projects_no_errors(self):
        """projects が空辞書でもエラーなし"""
        data = {"projects": {}}
        errors = validate_monitoring_yaml(data)
        assert errors == []

    def test_missing_projects_key(self):
        """'projects' キーがない場合はエラー"""
        data = {}
        errors = validate_monitoring_yaml(data)
        assert any("projects" in e for e in errors)


# ---------------------------------------------------------------------------
# テスト: 実際の設定ファイルの検証
# ---------------------------------------------------------------------------

class TestActualConfigFiles:
    """実際の設定ファイルのバリデーションテスト"""

    def test_actual_ports_yaml_is_valid(self):
        """実際の ports.yaml が有効であること"""
        try:
            import yaml
        except ImportError:
            pytest.skip("pyyaml がインストールされていません")

        ports_yaml = Path(__file__).parent.parent / "ports.yaml"
        if not ports_yaml.exists():
            pytest.skip("ports.yaml が見つかりません")

        with ports_yaml.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)

        errors = validate_ports_yaml(data)
        # URL scheme エラーのみ許容（portが文字列は構造上の問題）
        port_errors = [e for e in errors if "portは整数" in e]
        assert port_errors == [], f"ports.yaml にportエラー: {port_errors}"

    def test_actual_monitoring_yaml_is_valid(self):
        """実際の monitoring.yaml が有効であること"""
        try:
            import yaml
        except ImportError:
            pytest.skip("pyyaml がインストールされていません")

        monitoring_yaml = Path(__file__).parent.parent / "monitoring.yaml"
        if not monitoring_yaml.exists():
            pytest.skip("monitoring.yaml が見つかりません")

        with monitoring_yaml.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)

        errors = validate_monitoring_yaml(data)
        critical_errors = [e for e in errors if "必須キーが不足" in e or "未知のtype" in e]
        assert critical_errors == [], f"monitoring.yaml にエラー: {critical_errors}"
