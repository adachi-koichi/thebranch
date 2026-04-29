"""
Task #2548: サブスクリプション・プラン管理 API
- GET /api/subscriptions/plans - プランマスタ取得
- GET /api/subscriptions/current - 現在のサブスク取得（認証必須）
- PATCH /api/subscriptions/plan - プラン変更（認証必須）
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import sqlite3
import aiosqlite
from pathlib import Path

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])
DASHBOARD_DIR = Path(__file__).parent.parent
THEBRANCH_DB = DASHBOARD_DIR / "data" / "thebranch.sqlite"


class SubscriptionPlanFeatures(BaseModel):
    max_agents: int
    api_calls_per_month: int
    storage_gb: int
    email_support: bool
    priority_support: bool = False


class SubscriptionPlan(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price_jpy: int
    features: SubscriptionPlanFeatures


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    plan: str
    status: str
    current_period_start: str
    current_period_end: str
    canceled_at: Optional[str] = None
    created_at: str
    updated_at: str


class SubscriptionPlanListResponse(BaseModel):
    plans: List[SubscriptionPlan]


class SubscriptionPlanChangeRequest(BaseModel):
    plan: str


async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """認証ユーザーを取得"""
    from dashboard.app import verify_token_with_scope

    user_id, _, _ = await verify_token_with_scope(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@router.get("/plans", response_model=SubscriptionPlanListResponse)
async def get_subscription_plans():
    """利用可能なすべてのプランを取得（公開情報、認証不要）"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT code, name, '' as description, price_jpy FROM subscription_plans WHERE is_public = 1 ORDER BY sort_order"
            )
            plans_rows = await cursor.fetchall()

        plans = []
        for row in plans_rows:
            plan_id = row["code"]

            # 機能情報を取得
            features = {
                "free": {
                    "max_agents": 3,
                    "api_calls_per_month": 1000,
                    "storage_gb": 1,
                    "email_support": False,
                    "priority_support": False,
                },
                "starter": {
                    "max_agents": 10,
                    "api_calls_per_month": 10000,
                    "storage_gb": 10,
                    "email_support": True,
                    "priority_support": False,
                },
                "pro": {
                    "max_agents": 50,
                    "api_calls_per_month": 1000000,
                    "storage_gb": 100,
                    "email_support": True,
                    "priority_support": True,
                },
                "enterprise": {
                    "max_agents": 9999,
                    "api_calls_per_month": 9999999,
                    "storage_gb": 10000,
                    "email_support": True,
                    "priority_support": True,
                },
            }

            plan = SubscriptionPlan(
                id=plan_id,
                name=row["name"],
                description=row["description"] or None,
                price_jpy=row["price_jpy"],
                features=SubscriptionPlanFeatures(**features.get(plan_id, features["free"]))
            )
            plans.append(plan)

        return SubscriptionPlanListResponse(plans=plans)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(user_id: str = Depends(get_current_user)):
    """認証ユーザーの現在のサブスクリプション取得"""
    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT us.id, us.user_id, us.plan_code, us.status,
                       us.current_period_start, us.current_period_end,
                       us.canceled_at, us.created_at, us.updated_at
                FROM user_subscriptions us
                WHERE us.user_id = ? AND us.status IN ('active', 'trialing')
                LIMIT 1
                """,
                (user_id,)
            )
            sub_row = await cursor.fetchone()

        if not sub_row:
            # 初回ユーザーの場合、Free プランを自動作成
            now = datetime.now().isoformat()
            period_end = (datetime.now() + timedelta(days=30)).isoformat()

            async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
                await db.execute(
                    """
                    INSERT INTO user_subscriptions
                    (user_id, plan_code, status, started_at, current_period_start, current_period_end, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, "free", "active", now, now, period_end, now, now)
                )
                await db.commit()

                # 作成したレコードを再取得
                cursor = await db.execute(
                    """
                    SELECT id, user_id, plan_code, status,
                           current_period_start, current_period_end,
                           canceled_at, created_at, updated_at
                    FROM user_subscriptions
                    WHERE user_id = ? AND plan_code = 'free'
                    LIMIT 1
                    """,
                    (user_id,)
                )
                sub_row = await cursor.fetchone()

        if not sub_row:
            raise HTTPException(status_code=404, detail="Subscription not found for user")

        return SubscriptionResponse(
            id=f"sub-{sub_row['id']}",
            user_id=sub_row["user_id"],
            plan=sub_row["plan_code"],
            status=sub_row["status"],
            current_period_start=sub_row["current_period_start"],
            current_period_end=sub_row["current_period_end"],
            canceled_at=sub_row["canceled_at"],
            created_at=sub_row["created_at"],
            updated_at=sub_row["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.patch("/plan", response_model=SubscriptionResponse)
async def change_subscription_plan(
    request: SubscriptionPlanChangeRequest,
    user_id: str = Depends(get_current_user)
):
    """ユーザーのプランを変更"""
    new_plan = request.plan

    # バリデーション
    valid_plans = ["free", "starter", "pro", "enterprise"]
    if new_plan not in valid_plans:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan: '{new_plan}'. Valid plans: {', '.join(valid_plans)}"
        )

    try:
        async with aiosqlite.connect(str(THEBRANCH_DB)) as db:
            db.row_factory = aiosqlite.Row

            # 現在のプランを取得
            cursor = await db.execute(
                """
                SELECT id, plan_code, status
                FROM user_subscriptions
                WHERE user_id = ? AND status IN ('active', 'trialing')
                LIMIT 1
                """,
                (user_id,)
            )
            current_sub = await cursor.fetchone()

            if not current_sub:
                raise HTTPException(status_code=404, detail="Subscription not found for user")

            current_plan = current_sub["plan_code"]

            # 同じプランへの変更チェック
            if current_plan == new_plan:
                raise HTTPException(
                    status_code=400,
                    detail=f"User is already on {new_plan} plan"
                )

            # プラン変更を実行
            now = datetime.now().isoformat()
            period_end = (datetime.now() + timedelta(days=30)).isoformat()

            await db.execute(
                """
                UPDATE user_subscriptions
                SET plan_code = ?, current_period_start = ?, current_period_end = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_plan, now, period_end, now, current_sub["id"])
            )

            # イベント記録
            await db.execute(
                """
                INSERT INTO subscription_events
                (user_id, subscription_id, event_type, from_plan, to_plan, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, current_sub["id"], "upgraded" if valid_plans.index(new_plan) > valid_plans.index(current_plan) else "downgraded", current_plan, new_plan, "app")
            )

            await db.commit()

            # 更新後のサブスク情報を返却
            cursor = await db.execute(
                """
                SELECT id, user_id, plan_code, status,
                       current_period_start, current_period_end,
                       canceled_at, created_at, updated_at
                FROM user_subscriptions
                WHERE id = ?
                """,
                (current_sub["id"],)
            )
            updated_sub = await cursor.fetchone()

            return SubscriptionResponse(
                id=f"sub-{updated_sub['id']}",
                user_id=updated_sub["user_id"],
                plan=updated_sub["plan_code"],
                status=updated_sub["status"],
                current_period_start=updated_sub["current_period_start"],
                current_period_end=updated_sub["current_period_end"],
                canceled_at=updated_sub["canceled_at"],
                created_at=updated_sub["created_at"],
                updated_at=updated_sub["updated_at"],
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
