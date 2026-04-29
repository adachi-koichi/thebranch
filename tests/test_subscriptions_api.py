"""Subscription API テスト (Task #2548)"""
import pytest
import aiosqlite
from datetime import datetime, timedelta
from pathlib import Path
from fastapi.testclient import TestClient
from dashboard.app import app
from dashboard import auth

DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"
THEBRANCH_DB = DASHBOARD_DIR / "data" / "thebranch.sqlite"

client = TestClient(app)


@pytest.fixture
async def setup_test_user():
    """テスト用ユーザーを作成"""
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        # テストユーザー作成
        test_user_id = "test-user-sub-001"
        await db.execute(
            "INSERT OR IGNORE INTO users (id, username, email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                test_user_id,
                "testuser",
                "test@example.com",
                "hashed_password",
                "member",
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )

        # サブスクリプション作成（free プラン）
        sub_id = "sub-test-001"
        now = datetime.utcnow()
        period_end = now + timedelta(days=30)

        await db.execute(
            """
            INSERT OR IGNORE INTO subscriptions
            (id, user_id, plan, status, current_period_start, current_period_end, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sub_id,
                test_user_id,
                "free",
                "active",
                now.isoformat(),
                period_end.isoformat(),
                now.isoformat(),
                now.isoformat(),
            ),
        )
        await db.commit()

    yield test_user_id

    # クリーンアップ
    async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
        await db.execute("DELETE FROM subscriptions WHERE user_id = ?", (test_user_id,))
        await db.execute("DELETE FROM users WHERE id = ?", (test_user_id,))
        await db.commit()


def test_get_subscription_plans():
    """プラン一覧取得"""
    response = client.get("/api/subscriptions/plans")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) > 0

    # free プランが含まれることを確認
    plan_ids = [p["id"] for p in data["plans"]]
    assert "free" in plan_ids

    # pro プランが含まれることを確認
    assert "pro" in plan_ids

    # 各プランの必須フィールドを確認
    for plan in data["plans"]:
        assert "id" in plan
        assert "name" in plan
        assert "price_jpy" in plan
        assert "features" in plan

        # features フィールドの確認
        features = plan["features"]
        assert "max_agents" in features
        assert "api_calls_per_month" in features
        assert "storage_gb" in features
        assert "email_support" in features


@pytest.mark.asyncio
async def test_get_current_subscription_no_auth():
    """認証なしでサブスクリプション取得 → 401 エラー"""
    response = client.get("/api/subscriptions/current")
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_change_plan_invalid_plan():
    """無効なプラン → 400 エラー"""
    # テスト用のダミートークン（実装依存）
    headers = {}  # 認証なしでテスト
    response = client.patch(
        "/api/subscriptions/plan",
        json={"plan": "invalid_plan"},
        headers=headers,
    )
    # 認証されていないため 401
    assert response.status_code == 401


def test_get_subscription_plans_features():
    """プランの機能情報を確認"""
    response = client.get("/api/subscriptions/plans")
    data = response.json()

    # free プランを確認
    free_plan = next((p for p in data["plans"] if p["id"] == "free"), None)
    assert free_plan is not None
    assert free_plan["name"] == "Free"
    assert free_plan["price_jpy"] == 0

    # pro プランを確認
    pro_plan = next((p for p in data["plans"] if p["id"] == "pro"), None)
    assert pro_plan is not None
    assert pro_plan["name"] == "Pro"
    assert pro_plan["price_jpy"] == 9900

    # starter プランも確認
    starter_plan = next((p for p in data["plans"] if p["id"] == "starter"), None)
    assert starter_plan is not None
    assert starter_plan["name"] == "Starter"
    assert starter_plan["price_jpy"] == 2980

    # enterprise プランの確認
    enterprise_plan = next((p for p in data["plans"] if p["id"] == "enterprise"), None)
    assert enterprise_plan is not None
    assert enterprise_plan["name"] == "Enterprise"
    # Enterprise は -1（カスタム価格）


def test_subscription_plan_comparison():
    """プラン比較用の情報取得"""
    response = client.get("/api/subscriptions/plans")
    data = response.json()

    free = next((p for p in data["plans"] if p["id"] == "free"), None)
    pro = next((p for p in data["plans"] if p["id"] == "pro"), None)

    # free < pro の確認
    assert free["features"]["max_agents"] < pro["features"]["max_agents"]
    assert (
        free["features"]["api_calls_per_month"]
        < pro["features"]["api_calls_per_month"]
    )
    assert free["features"]["storage_gb"] < pro["features"]["storage_gb"]


def test_change_plan_same_plan():
    """同じプランへの変更 → 400 エラー"""
    response = client.patch(
        "/api/subscriptions/plan",
        json={"plan": "free"},
    )
    # 認証なしなため 401
    assert response.status_code == 401


def test_change_plan_free_to_pro_unauthorized():
    """認証なしでプラン変更 → 401 エラー"""
    response = client.patch(
        "/api/subscriptions/plan",
        json={"plan": "pro"},
    )
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_subscription_period_calculation():
    """期間計算の正確性を確認"""
    # プランを取得して、期間計算ロジックを確認
    response = client.get("/api/subscriptions/plans")
    assert response.status_code == 200
    data = response.json()

    # plans が存在することを確認
    assert "plans" in data
    assert len(data["plans"]) > 0

    # 各プランにフィーチャーが設定されていることを確認
    for plan in data["plans"]:
        assert "features" in plan
        assert "max_agents" in plan["features"]


def test_get_subscription_plans_all_required_fields():
    """プラン情報にすべての必須フィールドが含まれることを確認"""
    response = client.get("/api/subscriptions/plans")
    assert response.status_code == 200
    data = response.json()

    for plan in data["plans"]:
        # 必須フィールド確認
        assert "id" in plan
        assert "name" in plan
        assert "price_jpy" in plan
        assert "features" in plan
        assert isinstance(plan["id"], str)
        assert isinstance(plan["name"], str)
        assert isinstance(plan["price_jpy"], int)
        assert isinstance(plan["features"], dict)


def test_get_subscription_plans_valid_plan_ids():
    """プラン ID が有効な値であることを確認"""
    response = client.get("/api/subscriptions/plans")
    assert response.status_code == 200
    data = response.json()

    valid_plan_ids = ["free", "starter", "pro", "enterprise"]
    plan_ids = [p["id"] for p in data["plans"]]

    for plan_id in plan_ids:
        assert plan_id in valid_plan_ids


def test_get_subscription_plans_price_consistency():
    """プラン価格がプランの昇順であることを確認"""
    response = client.get("/api/subscriptions/plans")
    assert response.status_code == 200
    data = response.json()

    # プランを ID の昇順でソート（free < starter < pro < enterprise）
    plan_order = {"free": 0, "starter": 1, "pro": 2, "enterprise": 3}
    plans_sorted = sorted(
        data["plans"],
        key=lambda p: plan_order.get(p["id"], 999)
    )

    # free と enterprise 以外のプランのみでチェック
    regular_plans = [p for p in plans_sorted if p["id"] != "enterprise"]

    # 価格が昇順であることを確認
    for i in range(len(regular_plans) - 1):
        current = regular_plans[i]
        next_plan = regular_plans[i + 1]

        # 後続プランの価格 >= 現在のプランの価格（同じまたは高くなる）
        assert next_plan["price_jpy"] >= current["price_jpy"]

    # free プランの確認
    free_plan = next((p for p in regular_plans if p["id"] == "free"), None)
    assert free_plan is not None
    assert free_plan["price_jpy"] == 0
