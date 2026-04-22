"""
E2E テスト: オンボーディング全フロー
pytest-bdd を使用した Gherkin シナリオ実装
"""
import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import uuid
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

# Import app and models
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard import app as app_module
from dashboard import models, auth


@pytest.fixture
async def client():
    """AsyncClient を返す"""
    transport = ASGITransport(app=app_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_user():
    """テスト用ユーザーとトークンを作成"""
    user_id = str(uuid.uuid4())
    token = "test-token-" + str(uuid.uuid4())

    # auth.sqlite にユーザーとセッションを作成
    db_path = Path.home() / ".claude" / "dashboard_auth.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash)
            VALUES (?, ?, ?, ?)
        """, (user_id, f"test-{uuid.uuid4().hex[:8]}", f"test-{uuid.uuid4().hex[:8]}@example.com", "dummy"))

        expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        cursor.execute("""
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token, expires_at))

        conn.commit()
    finally:
        conn.close()

    return {"user_id": user_id, "token": token}


class TestOnboardingE2E:
    """E2E テストクラス"""

    @pytest.mark.asyncio
    async def test_vision_input_and_ai_analysis(self, client, test_user):
        """ビジョン入力 → AI分析開始"""
        vision = "高速成長する SaaS 企業向けの営業チームを作りたい"

        with patch("workflow.services.onboarding.get_onboarding_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.analyze_vision_for_templates.return_value = [
                {
                    "template_id": 2,
                    "name": "営業推進部",
                    "category": "Sales",
                    "total_roles": 5,
                    "total_processes": 7,
                    "reason": "営業成長に最適な部署構成",
                    "rank": 1
                }
            ]
            mock_service.return_value = mock_instance

            response = await client.post(
                "/api/onboarding/initialize",
                json={"vision_input": vision},
                headers={"Authorization": f"Bearer {test_user['token']}"}
            )

        assert response.status_code == 201
        data = response.json()
        assert "onboarding_id" in data
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0
        assert data["suggestions"][0]["name"] == "営業推進部"

    @pytest.mark.asyncio
    async def test_template_selection_and_detailed_setup(self, client, test_user):
        """テンプレート選択 → 詳細設定"""
        vision = "営業チームを立ち上げたい"

        # Step 1: AI分析
        with patch("workflow.services.onboarding.get_onboarding_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.analyze_vision_for_templates.return_value = [
                {
                    "template_id": 2,
                    "name": "営業",
                    "category": "Sales",
                    "total_roles": 5,
                    "total_processes": 7,
                    "reason": "営業チーム向け",
                    "rank": 1
                }
            ]
            mock_instance.validate_budget.return_value = {
                "status": "ok",
                "monthly_per_person": 5500.0,
                "market_benchmark": 5500,
                "message": "予算が適切です"
            }
            mock_service.return_value = mock_instance

            init_response = await client.post(
                "/api/onboarding/initialize",
                json={"vision_input": vision},
                headers={"Authorization": f"Bearer {test_user['token']}"}
            )

        assert init_response.status_code == 201
        onboarding_id = init_response.json()["onboarding_id"]

        # Step 2: 詳細設定
        with patch("workflow.services.onboarding.get_onboarding_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.validate_budget.return_value = {
                "status": "ok",
                "monthly_per_person": 5500.0,
                "market_benchmark": 5500,
                "message": "予算が適切です"
            }
            mock_service.return_value = mock_instance

            setup_response = await client.post(
                "/api/onboarding/setup",
                json={
                    "onboarding_id": onboarding_id,
                    "template_id": 2,
                    "dept_name": "営業推進部",
                    "manager_name": "田中太郎",
                    "members_count": 3,
                    "budget": 16500.0,
                    "kpi": "月商1000万円達成",
                    "integrations": {}
                },
                headers={"Authorization": f"Bearer {test_user['token']}"}
            )

        assert setup_response.status_code == 200
        data = setup_response.json()
        assert "dept_id" in data
        assert data["config_validated"] is True
        assert data["budget_validation"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_execute_onboarding_with_task_generation(self, client, test_user):
        """初期タスク実行 → タスク生成 → エージェント起動"""
        vision = "営業チームを立ち上げたい"

        # Step 1: AI分析
        with patch("workflow.services.onboarding.get_onboarding_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.analyze_vision_for_templates.return_value = [
                {
                    "template_id": 2,
                    "name": "営業",
                    "category": "Sales",
                    "total_roles": 5,
                    "total_processes": 7,
                    "reason": "営業チーム向け",
                    "rank": 1
                }
            ]
            mock_service.return_value = mock_instance

            init_response = await client.post(
                "/api/onboarding/initialize",
                json={"vision_input": vision},
                headers={"Authorization": f"Bearer {test_user['token']}"}
            )

        onboarding_id = init_response.json()["onboarding_id"]

        # Step 2: 詳細設定
        with patch("workflow.services.onboarding.get_onboarding_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.validate_budget.return_value = {
                "status": "ok",
                "monthly_per_person": 5500.0,
                "market_benchmark": 5500,
                "message": "予算が適切です"
            }
            mock_service.return_value = mock_instance

            setup_response = await client.post(
                "/api/onboarding/setup",
                json={
                    "onboarding_id": onboarding_id,
                    "template_id": 2,
                    "dept_name": "営業推進部",
                    "manager_name": "田中太郎",
                    "members_count": 3,
                    "budget": 16500.0,
                    "kpi": "月商1000万円達成",
                    "integrations": {}
                },
                headers={"Authorization": f"Bearer {test_user['token']}"}
            )

        dept_id = setup_response.json()["dept_id"]

        # Step 3: 実行
        with patch("workflow.services.onboarding.get_onboarding_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.generate_initial_tasks.return_value = [
                {
                    "task_id": "task_001",
                    "title": "営業チーム オンボーディング完了",
                    "description": "チームメンバーのシステムアクセス設定と基本教育",
                    "budget": 5500.0,
                    "deadline": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                    "assigned_to": "Manager"
                },
                {
                    "task_id": "task_002",
                    "title": "営業プロセス定義",
                    "description": "営業フロー、提案資料、価格体系の定義・文書化",
                    "budget": 5500.0,
                    "deadline": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
                    "assigned_to": "Lead"
                },
                {
                    "task_id": "task_003",
                    "title": "KPI ダッシュボード構築",
                    "description": "営業KPIの定義と月次レポート体制の構築",
                    "budget": 5500.0,
                    "deadline": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                    "assigned_to": "Analyst"
                }
            ]
            mock_service.return_value = mock_instance

            execute_response = await client.post(
                "/api/onboarding/execute",
                json={
                    "onboarding_id": onboarding_id,
                    "dept_id": dept_id
                },
                headers={"Authorization": f"Bearer {test_user['token']}"}
            )

        assert execute_response.status_code == 200
        data = execute_response.json()
        assert "tasks_created" in data
        assert len(data["tasks_created"]) == 3
        assert data["agent_status"] == "activating"
        assert "dashboard_url" in data

    @pytest.mark.asyncio
    async def test_vision_input_validation(self, client, test_user):
        """ビジョン入力バリデーション"""
        # テスト: 空のビジョン
        response = await client.post(
            "/api/onboarding/initialize",
            json={"vision_input": ""},
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 400
        assert "Vision input must be 10-500 characters" in response.json()["detail"]

        # テスト: 短すぎるビジョン
        response = await client.post(
            "/api/onboarding/initialize",
            json={"vision_input": "短い"},
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 400

        # テスト: 長すぎるビジョン
        long_vision = "a" * 501
        response = await client.post(
            "/api/onboarding/initialize",
            json={"vision_input": long_vision},
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_detailed_setup_validation(self, client, test_user):
        """詳細設定フェーズのバリデーション"""
        vision = "営業チームを立ち上げたい"

        # AI分析
        with patch("workflow.services.onboarding.get_onboarding_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.analyze_vision_for_templates.return_value = [
                {
                    "template_id": 2,
                    "name": "営業",
                    "category": "Sales",
                    "total_roles": 5,
                    "total_processes": 7,
                    "reason": "営業チーム向け",
                    "rank": 1
                }
            ]
            mock_service.return_value = mock_instance

            init_response = await client.post(
                "/api/onboarding/initialize",
                json={"vision_input": vision},
                headers={"Authorization": f"Bearer {test_user['token']}"}
            )

        onboarding_id = init_response.json()["onboarding_id"]

        # テスト: 必須項目なし
        response = await client.post(
            "/api/onboarding/setup",
            json={
                "onboarding_id": onboarding_id,
                "template_id": 2,
                "dept_name": "",  # 空
                "manager_name": "田中太郎",
                "members_count": 3,
                "budget": 16500.0,
                "kpi": "月商1000万円達成"
            },
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
        assert response.status_code == 400

        # テスト: 負のメンバー数
        with patch("workflow.services.onboarding.get_onboarding_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.validate_budget.return_value = {
                "status": "error",
                "monthly_per_person": 0,
                "market_benchmark": 5500,
                "message": "メンバー数が不適切です"
            }
            mock_service.return_value = mock_instance

            response = await client.post(
                "/api/onboarding/setup",
                json={
                    "onboarding_id": onboarding_id,
                    "template_id": 2,
                    "dept_name": "営業推進部",
                    "manager_name": "田中太郎",
                    "members_count": -1,  # 負の数
                    "budget": 16500.0,
                    "kpi": "月商1000万円達成"
                },
                headers={"Authorization": f"Bearer {test_user['token']}"}
            )
            assert response.status_code == 400
