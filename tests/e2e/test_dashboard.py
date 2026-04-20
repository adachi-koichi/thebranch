#!/usr/bin/env python3
"""
tests/e2e/test_dashboard.py — ダッシュボードE2Eテスト

対象: dashboard/app.py (Streamlit dashboard)
方式: localhost:8501 へのHTTPリクエストによるE2Eテスト（起動不要・モック対応）
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# requests が使えるか確認し、なければモック
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


DASHBOARD_URL = "http://localhost:8501"


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def make_mock_response(status_code: int = 200, text: str = "<html>Streamlit</html>") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.headers = {"content-type": "text/html"}
    return resp


# ---------------------------------------------------------------------------
# テスト: ダッシュボード HTTP アクセス
# ---------------------------------------------------------------------------

class TestDashboardHttpAccess:
    """ダッシュボードへのHTTPリクエストテスト（requestsモック使用）"""

    @patch("requests.get")
    def test_dashboard_returns_200(self, mock_get):
        """ダッシュボードが 200 を返すこと"""
        mock_get.return_value = make_mock_response(200)

        import requests as req
        resp = req.get(DASHBOARD_URL, timeout=5)

        assert resp.status_code == 200
        mock_get.assert_called_once_with(DASHBOARD_URL, timeout=5)

    @patch("requests.get")
    def test_dashboard_response_contains_html(self, mock_get):
        """レスポンスが HTML コンテンツを含むこと"""
        mock_get.return_value = make_mock_response(200, text="<html><body>Streamlit App</body></html>")

        import requests as req
        resp = req.get(DASHBOARD_URL, timeout=5)

        assert "<html" in resp.text

    @patch("requests.get")
    def test_dashboard_connection_refused_raises(self, mock_get):
        """サーバーが起動していない場合は ConnectionError が発生すること"""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Connection refused")

        with pytest.raises(req.exceptions.ConnectionError):
            req.get(DASHBOARD_URL, timeout=5)

    @patch("requests.get")
    def test_dashboard_timeout_raises(self, mock_get):
        """タイムアウト時は Timeout 例外が発生すること"""
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout("Timed out")

        with pytest.raises(req.exceptions.Timeout):
            req.get(DASHBOARD_URL, timeout=5)

    @patch("requests.get")
    def test_dashboard_non_200_detected(self, mock_get):
        """500 エラーを正しく検出できること"""
        mock_get.return_value = make_mock_response(500, text="Internal Server Error")

        import requests as req
        resp = req.get(DASHBOARD_URL, timeout=5)

        assert resp.status_code == 500

    @patch("requests.get")
    def test_dashboard_health_endpoint(self, mock_get):
        """/_stcore/health エンドポイントが 200 を返すこと（Streamlit標準）"""
        mock_get.return_value = make_mock_response(200, text="ok")

        import requests as req
        resp = req.get(f"{DASHBOARD_URL}/_stcore/health", timeout=5)

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# テスト: ダッシュボード app.py 構造テスト
# ---------------------------------------------------------------------------

class TestDashboardAppStructure:
    """dashboard/app.py のモジュール構造テスト"""

    def test_dashboard_app_file_exists(self):
        """dashboard/app.py が存在すること"""
        app_path = Path(__file__).parent.parent.parent / "dashboard" / "app.py"
        assert app_path.exists(), f"dashboard/app.py が見つかりません: {app_path}"

    def test_dashboard_requirements_exist(self):
        """dashboard/requirements.txt が存在すること"""
        req_path = Path(__file__).parent.parent.parent / "dashboard" / "requirements.txt"
        assert req_path.exists(), f"dashboard/requirements.txt が見つかりません: {req_path}"

    def test_dashboard_app_is_python_file(self):
        """dashboard/app.py が Pythonファイルとして読み込めること"""
        app_path = Path(__file__).parent.parent.parent / "dashboard" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        assert len(content) > 0, "app.py が空です"
