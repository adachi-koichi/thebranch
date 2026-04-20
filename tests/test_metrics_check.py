#!/usr/bin/env python3
"""
tests/test_metrics_check.py — metrics_check.py のユニットテスト

対象: scripts/metrics_check.py
      - load_monitoring_yaml()
      - find_datetime_column()
      - check_sqlite_metric()
      - check_log_metric()
      - main() ロジック
"""

import json
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import metrics_check
from metrics_check import (
    load_monitoring_yaml,
    find_datetime_column,
    check_sqlite_metric,
    check_log_metric,
    MONITORING_YAML,
)


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_db_with_data(tmp_path):
    """テスト用SQLiteDBを作成し、created_at 付きのデータを挿入する。"""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE records (id INTEGER PRIMARY KEY, created_at TEXT, value REAL)"
    )
    # 直近60分以内に10件のデータを挿入
    now = datetime.now(timezone.utc)
    for i in range(10):
        dt = (now - timedelta(minutes=i * 3)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO records (created_at, value) VALUES (?, ?)", (dt, i * 1.5))
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def sqlite_db_stale(tmp_path):
    """古いデータのみのSQLiteDBを作成する。"""
    db = tmp_path / "stale.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE records (id INTEGER PRIMARY KEY, created_at TEXT, value REAL)"
    )
    # 2時間前のデータのみ
    old_dt = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO records (created_at, value) VALUES (?, ?)", (old_dt, 1.0))
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def log_file_fresh(tmp_path):
    """直近に更新されたログファイル（10行）を作成する。"""
    log_file = tmp_path / "fresh.log"
    lines = "\n".join(f"2026-04-17 10:0{i}:00 INFO message {i}" for i in range(10))
    log_file.write_text(lines, encoding="utf-8")
    return log_file


@pytest.fixture
def log_file_stale(tmp_path):
    """古いタイムスタンプのログファイルを作成する。"""
    log_file = tmp_path / "stale.log"
    log_file.write_text("old log line\n", encoding="utf-8")
    # ファイルの最終更新時刻を2時間前に設定
    old_time = time.time() - 7200
    import os
    os.utime(str(log_file), (old_time, old_time))
    return log_file


# ---------------------------------------------------------------------------
# テスト: load_monitoring_yaml()
# ---------------------------------------------------------------------------

class TestLoadMonitoringYaml:
    """load_monitoring_yaml() のテスト"""

    def test_loads_valid_yaml(self, tmp_path):
        """正常な YAML を読み込めること"""
        yaml_content = """
projects:
  test-proj:
    metrics:
      - name: テストDB
        type: sqlite
        path: /tmp/test.db
        interval_minutes: 60
        min_records: 5
"""
        yaml_file = tmp_path / "monitoring.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        with patch.object(metrics_check, "MONITORING_YAML", yaml_file):
            data = load_monitoring_yaml()

        assert "projects" in data
        assert "test-proj" in data["projects"]

    def test_loads_actual_monitoring_yaml(self):
        """実際の monitoring.yaml が読み込めること"""
        if not MONITORING_YAML.exists():
            pytest.skip("monitoring.yaml が見つかりません")
        data = load_monitoring_yaml()
        assert isinstance(data, dict)

    def test_missing_file_raises(self, tmp_path):
        """存在しないファイルは例外を発生させること"""
        missing = tmp_path / "nonexistent.yaml"
        with patch.object(metrics_check, "MONITORING_YAML", missing):
            with pytest.raises(FileNotFoundError):
                load_monitoring_yaml()


# ---------------------------------------------------------------------------
# テスト: find_datetime_column()
# ---------------------------------------------------------------------------

class TestFindDatetimeColumn:
    """find_datetime_column() のテスト"""

    def test_finds_created_at_column(self, tmp_path):
        """created_at カラムが優先的に見つかること"""
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER, created_at TEXT, value TEXT)")
        cursor = conn.cursor()

        result = find_datetime_column(cursor, "t")
        conn.close()

        assert result == "created_at"

    def test_finds_updated_at_when_no_created_at(self, tmp_path):
        """created_at がない場合は updated_at が見つかること"""
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER, updated_at TEXT, value TEXT)")
        cursor = conn.cursor()

        result = find_datetime_column(cursor, "t")
        conn.close()

        assert result == "updated_at"

    def test_returns_none_when_no_datetime_column(self, tmp_path):
        """日時カラムがない場合は None を返すこと"""
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER, name TEXT, value REAL)")
        cursor = conn.cursor()

        result = find_datetime_column(cursor, "t")
        conn.close()

        assert result is None


# ---------------------------------------------------------------------------
# テスト: check_sqlite_metric()
# ---------------------------------------------------------------------------

class TestCheckSqliteMetric:
    """check_sqlite_metric() のテスト"""

    def test_returns_none_when_ok(self, sqlite_db_with_data):
        """最新データが十分ある場合は None を返すこと"""
        metric = {
            "name": "テストDB",
            "path": str(sqlite_db_with_data),
            "table": "records",
            "interval_minutes": 60,
            "min_records": 5,
        }
        result = check_sqlite_metric("test-proj", metric)
        assert result is None

    def test_returns_error_when_stale(self, sqlite_db_stale):
        """古いデータしかない場合はエラーdictを返すこと"""
        metric = {
            "name": "古いDB",
            "path": str(sqlite_db_stale),
            "table": "records",
            "interval_minutes": 60,  # 60分以内
            "min_records": 1,
        }
        result = check_sqlite_metric("test-proj", metric)
        assert result is not None
        assert result["project"] == "test-proj"
        assert result["metric"] == "古いDB"

    def test_returns_none_when_file_not_exists(self, tmp_path):
        """DBファイルが存在しない場合は None を返すこと（スキップ）"""
        metric = {
            "name": "nonexistent",
            "path": str(tmp_path / "nonexistent.db"),
            "table": "records",
            "interval_minutes": 60,
            "min_records": 1,
        }
        result = check_sqlite_metric("test-proj", metric)
        assert result is None

    def test_error_dict_has_required_fields(self, sqlite_db_stale):
        """エラーdictに必須フィールドが含まれること"""
        metric = {
            "name": "テスト",
            "path": str(sqlite_db_stale),
            "table": "records",
            "interval_minutes": 1,  # 1分以内 → 必ずエラー
            "min_records": 1,
        }
        result = check_sqlite_metric("my-proj", metric)

        if result is not None:
            required = {"project", "metric", "expected", "actual", "error"}
            assert required.issubset(result.keys())


# ---------------------------------------------------------------------------
# テスト: check_log_metric()
# ---------------------------------------------------------------------------

class TestCheckLogMetric:
    """check_log_metric() のテスト"""

    def test_returns_none_when_log_is_fresh_and_sufficient(self, log_file_fresh):
        """新鮮で行数が十分なログは None を返すこと"""
        metric = {
            "name": "テストログ",
            "path": str(log_file_fresh),
            "interval_minutes": 60,
            "min_records": 5,
        }
        result = check_log_metric("test-proj", metric)
        assert result is None

    def test_returns_error_when_log_is_stale(self, log_file_stale):
        """古いログファイルはエラーdictを返すこと"""
        metric = {
            "name": "古いログ",
            "path": str(log_file_stale),
            "interval_minutes": 60,  # 60分以内
            "min_records": 1,
        }
        result = check_log_metric("test-proj", metric)
        assert result is not None
        assert "分前に更新" in result["actual"]

    def test_returns_none_when_file_not_exists(self, tmp_path):
        """ログファイルが存在しない場合は None を返すこと（スキップ）"""
        metric = {
            "name": "nonexistent",
            "path": str(tmp_path / "nonexistent.log"),
            "interval_minutes": 60,
            "min_records": 1,
        }
        result = check_log_metric("test-proj", metric)
        assert result is None

    def test_returns_error_when_insufficient_lines(self, tmp_path):
        """行数が不足するログはエラーdictを返すこと"""
        log_file = tmp_path / "short.log"
        log_file.write_text("line1\n", encoding="utf-8")

        metric = {
            "name": "短いログ",
            "path": str(log_file),
            "interval_minutes": 60,
            "min_records": 10,
        }
        result = check_log_metric("test-proj", metric)
        assert result is not None
        assert "行" in result["actual"]


# ---------------------------------------------------------------------------
# テスト: main() ロジック（モック使用）
# ---------------------------------------------------------------------------

class TestMainLogic:
    """main() の統合ロジックテスト"""

    @patch("metrics_check.load_monitoring_yaml")
    @patch("metrics_check.check_sqlite_metric")
    def test_main_no_errors_outputs_ok_true(self, mock_check, mock_load, capsys):
        """エラーなしのとき ok=true を出力すること"""
        mock_load.return_value = {
            "projects": {
                "test-proj": {
                    "metrics": [
                        {
                            "name": "テストDB",
                            "type": "sqlite",
                            "path": "/tmp/test.db",
                            "interval_minutes": 60,
                            "min_records": 5,
                        }
                    ]
                }
            }
        }
        mock_check.return_value = None

        try:
            metrics_check.main()
        except SystemExit as e:
            assert e.code == 0 or e.code is None

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["ok"] is True
        assert output["errors"] == []

    @patch("metrics_check.load_monitoring_yaml")
    @patch("metrics_check.check_sqlite_metric")
    def test_main_with_errors_exits_1(self, mock_check, mock_load, capsys):
        """エラーありのとき exit code 1 で ok=false を出力すること"""
        mock_load.return_value = {
            "projects": {
                "test-proj": {
                    "metrics": [
                        {
                            "name": "古いDB",
                            "type": "sqlite",
                            "path": "/tmp/stale.db",
                            "interval_minutes": 60,
                            "min_records": 5,
                        }
                    ]
                }
            }
        }
        mock_check.return_value = {
            "project": "test-proj",
            "metric": "古いDB",
            "expected": "60分以内に5件以上",
            "actual": "0件",
            "error": None,
        }

        with pytest.raises(SystemExit) as exc_info:
            metrics_check.main()
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["ok"] is False
        assert len(output["errors"]) == 1

    @patch("metrics_check.load_monitoring_yaml")
    def test_main_unknown_metric_type_reported(self, mock_load, capsys):
        """未知のメトリクスタイプはエラーとして報告されること"""
        mock_load.return_value = {
            "projects": {
                "proj": {
                    "metrics": [
                        {
                            "name": "謎メトリクス",
                            "type": "unknown",
                            "path": "/tmp/test",
                            "interval_minutes": 60,
                            "min_records": 1,
                        }
                    ]
                }
            }
        }

        with pytest.raises(SystemExit) as exc_info:
            metrics_check.main()
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["ok"] is False
        assert any("未知" in e.get("error", "") for e in output["errors"])

    @patch("metrics_check.load_monitoring_yaml")
    def test_main_empty_projects_ok(self, mock_load, capsys):
        """projects が空の場合は ok=true であること"""
        mock_load.return_value = {"projects": {}}

        try:
            metrics_check.main()
        except SystemExit as e:
            assert e.code == 0 or e.code is None

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["ok"] is True
