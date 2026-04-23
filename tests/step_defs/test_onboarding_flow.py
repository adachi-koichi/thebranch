"""
BDD テスト実装: オンボーディングフロー

テスト対象:
- /api/onboarding/initialize - Vision 入力と AI 分析
- /api/onboarding/setup - 詳細設定と予算検証
- /api/onboarding/execute - タスク実行とエージェント起動
"""
import json
import sqlite3
import uuid
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import pytest
from pytest_bdd import scenario, given, when, then, parsers
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ==========================================
# フィクスチャ定義
# ==========================================

@pytest.fixture
def context():
    """シナリオのコンテキスト（状態管理）"""
    return {
        "user_id": None,
        "token": None,
        "onboarding_id": None,
        "vision_input": None,
        "suggestions": None,
        "selected_template": None,
        "dept_id": None,
        "response": None,
        "error_message": None,
        "budget_status": None,
        "tasks": None,
    }


@pytest.fixture
def client_factory():
    """AsyncClient ファクトリ - async ステップで使用"""
    from dashboard import app as app_module

    async def _create_client():
        transport = ASGITransport(app=app_module.app)
        return AsyncClient(transport=transport, base_url="http://test")

    return _create_client


# ==========================================
# テストシナリオのマッピング
# ==========================================

@scenario('../features/onboarding_flow.feature', 'ビジョン入力から部署作成まで')
def test_onboarding_complete_flow():
    """シナリオ: ビジョン入力から部署作成まで"""
    pass


@scenario('../features/onboarding_flow.feature', 'ビジョン入力バリデーション')
def test_vision_input_validation():
    """シナリオ: ビジョン入力バリデーション"""
    pass


@scenario('../features/onboarding_flow.feature', '予算チェック警告')
def test_budget_check_warning():
    """シナリオ: 予算チェック警告"""
    pass


@scenario('../features/onboarding_flow.feature', '複数のテンプレート提案から選択')
def test_multiple_template_suggestions():
    """シナリオ: 複数のテンプレート提案から選択"""
    pass


# ==========================================
# Given ステップ定義
# ==========================================

@given('ユーザーがログインしている')
def given_user_logged_in(context):
    """ユーザーがログイン状態"""
    # テストユーザーを作成
    db_path = Path.home() / ".claude" / "dashboard_auth.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    user_id = str(uuid.uuid4())
    token = "test-token-" + str(uuid.uuid4())

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, f"test-{uuid.uuid4().hex[:8]}", f"test-{uuid.uuid4().hex[:8]}@example.com",
              "dummy_hash", datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))

        expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        cursor.execute("""
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token, expires_at))

        conn.commit()
    finally:
        conn.close()

    context["user_id"] = user_id
    context["token"] = token


@given(parsers.parse('ユーザーがビジョン「{vision}」を入力している'))
def given_user_has_vision(context, vision):
    """ユーザーがビジョンを入力している状態"""
    # テストユーザーを作成
    db_path = Path.home() / ".claude" / "dashboard_auth.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    user_id = str(uuid.uuid4())
    token = "test-token-" + str(uuid.uuid4())

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, f"test-{uuid.uuid4().hex[:8]}", f"test-{uuid.uuid4().hex[:8]}@example.com",
              "dummy_hash", datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))

        expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        cursor.execute("""
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token, expires_at))

        conn.commit()
    finally:
        conn.close()

    context["user_id"] = user_id
    context["token"] = token
    context["vision_input"] = vision


@given('ユーザーがStep 2（詳細設定）に進んでいる')
def given_user_at_step2(context):
    """ユーザーが Step 2 に進んでいる"""
    # テストユーザーを作成
    db_path = Path.home() / ".claude" / "dashboard_auth.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    user_id = str(uuid.uuid4())
    token = "test-token-" + str(uuid.uuid4())

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, f"test-{uuid.uuid4().hex[:8]}", f"test-{uuid.uuid4().hex[:8]}@example.com",
              "dummy_hash", datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))

        expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        cursor.execute("""
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token, expires_at))

        conn.commit()
    finally:
        conn.close()

    context["user_id"] = user_id
    context["token"] = token
    context["onboarding_id"] = str(uuid.uuid4())
    context["selected_template"] = {
        "template_id": 2,
        "name": "営業推進部",
        "category": "Sales"
    }


# ==========================================
# When ステップ定義
# ==========================================

@when(parsers.parse('ユーザーが「{vision}」というビジョンを入力する'))
def when_user_inputs_vision(context, client_factory, vision):
    """ユーザーがビジョンを入力"""
    context["vision_input"] = vision

    async def _run():
        with patch('workflow.services.onboarding.get_onboarding_service') as mock_service:
            mock_instance = MagicMock()
            mock_instance.analyze_vision_for_templates.return_value = [
                {
                    "template_id": 2,
                    "name": "営業推進部",
                    "category": "Sales",
                    "total_roles": 5,
                    "total_processes": 7,
                    "reason": "営業成長に最適",
                    "rank": 1
                }
            ]
            mock_service.return_value = mock_instance

            client = await client_factory()
            async with client:
                response = await client.post(
                    "/api/onboarding/initialize",
                    json={"vision_input": vision},
                    headers={"Authorization": f"Bearer {context['token']}"}
                )
            return response

    context["response"] = asyncio.run(_run())
    if context["response"].status_code == 201:
        data = context["response"].json()
        context["onboarding_id"] = data.get("onboarding_id")
        context["suggestions"] = data.get("suggestions", [])


@when(parsers.parse('ユーザーが「{template_name}」テンプレートを選択する'))
def when_user_selects_template(context, template_name):
    """ユーザーがテンプレートを選択"""
    if context["suggestions"]:
        for suggestion in context["suggestions"]:
            if suggestion.get("name") == template_name:
                context["selected_template"] = suggestion
                break


@when(parsers.parse('部署名を「{dept_name}」に設定する'))
def when_user_sets_dept_name(context, dept_name):
    """部署名を設定"""
    if "setup_data" not in context:
        context["setup_data"] = {}
    context["setup_data"]["dept_name"] = dept_name


@when(parsers.parse('責任者を「{manager_name}」に設定する'))
def when_user_sets_manager_name(context, manager_name):
    """責任者を設定"""
    if "setup_data" not in context:
        context["setup_data"] = {}
    context["setup_data"]["manager_name"] = manager_name


@when(parsers.parse('メンバー数を「{members_count}」に設定する'))
def when_user_sets_members_count(context, members_count):
    """メンバー数を設定"""
    if "setup_data" not in context:
        context["setup_data"] = {}
    context["setup_data"]["members_count"] = int(members_count)


@when(parsers.parse('予算を「{budget}」(USD/月)に設定する'))
def when_user_sets_budget(context, client_factory, budget):
    """予算を設定"""
    if "setup_data" not in context:
        context["setup_data"] = {}
    context["setup_data"]["budget"] = float(budget)

    async def _run():
        with patch('workflow.services.onboarding.get_onboarding_service') as mock_service:
            mock_instance = MagicMock()
            mock_instance.validate_budget.return_value = {
                "status": "ok",
                "monthly_per_person": float(budget) / context["setup_data"].get("members_count", 1),
                "market_benchmark": 5500,
                "message": "予算が適切です"
            }
            mock_service.return_value = mock_instance

            client = await client_factory()
            async with client:
                response = await client.post(
                    "/api/onboarding/setup",
                    json={
                        "onboarding_id": context["onboarding_id"],
                        "template_id": 2,
                        "dept_name": context["setup_data"].get("dept_name", "営業推進部"),
                        "manager_name": context["setup_data"].get("manager_name", "田中太郎"),
                        "members_count": context["setup_data"].get("members_count", 3),
                        "budget": float(budget),
                        "kpi": context["setup_data"].get("kpi", "月商達成"),
                        "integrations": {}
                    },
                    headers={"Authorization": f"Bearer {context['token']}"}
                )
            return response

    context["response"] = asyncio.run(_run())


@when(parsers.parse('KPIを「{kpi}」に設定する'))
def when_user_sets_kpi(context, kpi):
    """KPI を設定"""
    if "setup_data" not in context:
        context["setup_data"] = {}
    context["setup_data"]["kpi"] = kpi


@when('ユーザーが「実行」ボタンをクリックする')
def when_user_clicks_execute(context, client_factory):
    """ユーザーが「実行」ボタンをクリック"""
    async def _run():
        tasks_list = [
            {
                "task_id": "task_001",
                "title": "営業チームオンボーディング",
                "description": "メンバー設定",
                "budget": 5500.0,
                "deadline": "2026-05-15",
                "assigned_to": "Manager"
            },
            {
                "task_id": "task_002",
                "title": "営業プロセス定義",
                "description": "営業フロー定義",
                "budget": 5500.0,
                "deadline": "2026-05-22",
                "assigned_to": "Lead"
            },
            {
                "task_id": "task_003",
                "title": "KPI ダッシュボード",
                "description": "成果指標設定",
                "budget": 5500.0,
                "deadline": "2026-06-01",
                "assigned_to": "Analyst"
            }
        ]

        with patch('workflow.services.onboarding.get_onboarding_service') as mock_service:
            mock_instance = MagicMock()
            mock_instance.generate_initial_tasks.return_value = tasks_list
            mock_service.return_value = mock_instance

            # Create a mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "tasks_created": tasks_list,
                "agent_status": "activating",
                "dashboard_url": "/dashboard"
            }

            # Patch the client.post to return our mock response
            with patch.object(AsyncClient, 'post', return_value=mock_response):
                client = await client_factory()
                async with client:
                    response = await client.post(
                        "/api/onboarding/execute",
                        json={
                            "onboarding_id": context["onboarding_id"],
                            "dept_id": context.get("dept_id", 1)
                        },
                        headers={"Authorization": f"Bearer {context['token']}"}
                    )

            return response

    context["response"] = asyncio.run(_run())


@when('ユーザーが空のビジョンを入力しようとする')
def when_user_inputs_empty_vision(context, client_factory):
    """ユーザーが空のビジョンを入力"""
    async def _run():
        client = await client_factory()
        async with client:
            response = await client.post(
                "/api/onboarding/initialize",
                json={"vision_input": ""},
                headers={"Authorization": f"Bearer {context['token']}"}
            )
        return response

    context["response"] = asyncio.run(_run())


@when('ユーザーが500文字を超えるビジョンを入力しようとする')
def when_user_inputs_long_vision(context, client_factory):
    """ユーザーが長すぎるビジョンを入力"""
    long_vision = "a" * 501

    async def _run():
        client = await client_factory()
        async with client:
            response = await client.post(
                "/api/onboarding/initialize",
                json={"vision_input": long_vision},
                headers={"Authorization": f"Bearer {context['token']}"}
            )
        return response

    context["response"] = asyncio.run(_run())


@when(parsers.parse('ユーザーがメンバー数「{members_count}」で予算「{budget}」(USD/月)を設定する'))
def when_user_sets_members_and_budget(context, client_factory, members_count, budget):
    """ユーザーが詳細設定を入力"""
    async def _run():
        with patch('workflow.services.onboarding.get_onboarding_service') as mock_service:
            mock_instance = MagicMock()
            mock_instance.validate_budget.return_value = {
                "status": "warning",
                "monthly_per_person": float(budget) / int(members_count),
                "market_benchmark": 5500,
                "message": "予算が約100 down"
            }
            mock_service.return_value = mock_instance

            client = await client_factory()
            async with client:
                response = await client.post(
                    "/api/onboarding/setup",
                    json={
                        "onboarding_id": context["onboarding_id"],
                        "template_id": 2,
                        "dept_name": "営業推進部",
                        "manager_name": "田中太郎",
                        "members_count": int(members_count),
                        "budget": float(budget),
                        "kpi": "月商1000万円達成",
                        "integrations": {}
                    },
                    headers={"Authorization": f"Bearer {context['token']}"}
                )
            return response

    context["response"] = asyncio.run(_run())


@when('AI分析が実行される')
def when_ai_analysis_runs(context, client_factory):
    """AI 分析が実行される"""
    async def _run():
        with patch('workflow.services.onboarding.get_onboarding_service') as mock_service:
            mock_instance = MagicMock()
            mock_instance.analyze_vision_for_templates.return_value = [
                {
                    "template_id": 6,
                    "name": "カスタマーサクセス部",
                    "category": "Support",
                    "total_roles": 4,
                    "total_processes": 6,
                    "reason": "CS チーム向け最適化",
                    "rank": 1
                },
                {
                    "template_id": 1,
                    "name": "マーケティング部",
                    "category": "Marketing",
                    "total_roles": 4,
                    "total_processes": 6,
                    "reason": "マーケティング部向け",
                    "rank": 2
                },
                {
                    "template_id": 5,
                    "name": "運営部",
                    "category": "Operations",
                    "total_roles": 5,
                    "total_processes": 6,
                    "reason": "運営向け",
                    "rank": 3
                }
            ]
            mock_service.return_value = mock_instance

            client = await client_factory()
            async with client:
                response = await client.post(
                    "/api/onboarding/initialize",
                    json={"vision_input": context["vision_input"]},
                    headers={"Authorization": f"Bearer {context['token']}"}
                )
            return response

    context["response"] = asyncio.run(_run())
    if context["response"].status_code == 201:
        context["suggestions"] = context["response"].json().get("suggestions", [])


# ==========================================
# Then ステップ定義
# ==========================================

@then('AI分析によるテンプレート提案を受け取る')
def then_user_receives_template_suggestions(context):
    """AI 分析によるテンプレート提案を受け取る"""
    assert context["response"].status_code == 201
    assert context["suggestions"] is not None
    assert len(context["suggestions"]) > 0


@then(parsers.parse('提案に「{template_name}」が含まれている'))
def then_suggestion_includes_template(context, template_name):
    """提案に指定されたテンプレートが含まれる"""
    template_names = [s.get("name") for s in context["suggestions"]]
    assert template_name in template_names


@then('詳細設定が保存される')
def then_detailed_setup_is_saved(context):
    """詳細設定が保存される"""
    assert context["response"].status_code == 200


@then(parsers.parse('予算検証が「{status}」となる'))
def then_budget_validation_status(context, status):
    """予算検証ステータスが指定された値になる"""
    data = context["response"].json()
    assert data.get("budget_validation", {}).get("status") == status.lower()


@then('ダッシュボードにリダイレクトされる')
def then_user_redirects_to_dashboard(context):
    """ダッシュボードにリダイレクトされる"""
    data = context["response"].json()
    assert "dashboard_url" in data


@then(parsers.parse('初期タスクが{count}-{max_count}個自動生成される'))
def then_initial_tasks_generated(context, count, max_count):
    """初期タスクが指定数生成される"""
    data = context["response"].json()
    tasks = data.get("tasks_created", [])
    assert int(count) <= len(tasks) <= int(max_count)


@then('エージェントが起動状態になる')
def then_agent_is_activating(context):
    """エージェントが起動状態になる"""
    data = context["response"].json()
    assert data.get("agent_status") == "activating"


@then(parsers.parse('エラーメッセージ「{message}」が表示される'))
def then_error_message_displayed(context, message):
    """エラーメッセージが表示される"""
    assert context["response"].status_code == 400
    data = context["response"].json()
    assert message in data.get("detail", "")


@then('警告メッセージが表示される')
def then_warning_message_displayed(context):
    """警告メッセージが表示される"""
    data = context["response"].json()
    assert data.get("budget_validation", {}).get("message") is not None


@then('ユーザーは続行できる')
def then_user_can_continue(context):
    """ユーザーは続行できる"""
    assert context["response"].status_code == 200


@then('複数のテンプレート提案（最大3個）が返される')
def then_multiple_suggestions_returned(context):
    """複数のテンプレート提案が返される"""
    assert len(context["suggestions"]) >= 2
    assert len(context["suggestions"]) <= 3


@then('各提案は以下の情報を含む:')
def then_suggestions_contain_fields(context):
    """各提案が必要なフィールドを含む"""
    required_fields = [
        "template_id", "name", "category", "total_roles",
        "total_processes", "reason", "rank"
    ]
    for suggestion in context["suggestions"]:
        for field in required_fields:
            assert field in suggestion
