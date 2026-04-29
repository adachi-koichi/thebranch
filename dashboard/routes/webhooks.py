import sqlite3
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from dashboard import auth
from dashboard.models import (
    WebhookSubscriptionCreate,
    WebhookSubscriptionResponse,
    WebhookListResponse,
)

TASKS_DB = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "data" / "tasks.sqlite"

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def get_db_connection():
    """Get SQLite database connection"""
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    return conn


async def verify_bearer_token(authorization: str = Header(None)) -> str:
    """Bearer Token 検証（簡略版）"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")
    return authorization.replace("Bearer ", "")


@router.post("/register", response_model=WebhookSubscriptionResponse, status_code=201)
async def register_webhook(
    data: WebhookSubscriptionCreate,
    token: str = Depends(verify_bearer_token),
) -> WebhookSubscriptionResponse:
    """Webhook 登録"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # バリデーション
        if not data.target_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Invalid target URL format")

        if data.auth_type not in ("bearer", "hmac-sha256"):
            raise HTTPException(status_code=400, detail="Invalid auth_type")

        if data.event_type != "task.completed":
            raise HTTPException(status_code=400, detail="Only task.completed event is supported")

        # シークレット ハッシュ化
        secret_hash = auth.hash_password(data.secret_key)

        # Webhook ID 生成
        webhook_id = f"wh_{uuid.uuid4().hex[:20]}"

        # リトライポリシー JSON 化
        retry_policy = data.retry_policy or {}
        retry_policy_json = json.dumps({
            "max_retries": retry_policy.get("max_retries", 3),
            "retry_backoff_ms": retry_policy.get("retry_backoff_ms", 1000),
            "timeout_ms": retry_policy.get("timeout_ms", 5000),
        })

        # カスタムヘッダ JSON 化
        custom_headers_json = json.dumps(data.headers) if data.headers else None

        # DB に挿入
        cursor.execute(
            """
            INSERT INTO webhook_subscriptions (
                webhook_id, user_id, name, event_type, target_url,
                auth_type, secret_key_hash, is_active, retry_policy,
                custom_headers, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                webhook_id,
                token,  # user_id として token を使用
                data.name,
                data.event_type,
                data.target_url,
                data.auth_type,
                secret_hash,
                1 if data.is_active else 0,
                retry_policy_json,
                custom_headers_json,
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()

        return WebhookSubscriptionResponse(
            webhook_id=webhook_id,
            name=data.name,
            event_type=data.event_type,
            target_url=data.target_url,
            is_active=data.is_active,
            created_at=datetime.utcnow().isoformat(),
            last_triggered_at=None,
            trigger_count=0,
        )

    finally:
        conn.close()


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: str,
    token: str = Depends(verify_bearer_token),
) -> None:
    """Webhook 削除"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 指定された webhook_id が存在し、かつ user_id が一致するか確認
        cursor.execute(
            "SELECT user_id FROM webhook_subscriptions WHERE webhook_id = ?",
            (webhook_id,),
        )
        webhook = cursor.fetchone()

        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        if webhook["user_id"] != token:
            raise HTTPException(status_code=403, detail="Not authorized to delete this webhook")

        cursor.execute("DELETE FROM webhook_subscriptions WHERE webhook_id = ?", (webhook_id,))
        conn.commit()

    finally:
        conn.close()


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    event_type: Optional[str] = "task.completed",
    token: str = Depends(verify_bearer_token),
) -> WebhookListResponse:
    """Webhook 一覧取得"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if event_type:
            cursor.execute(
                """
                SELECT webhook_id, name, event_type, target_url, is_active,
                       created_at, last_triggered_at, trigger_count
                FROM webhook_subscriptions
                WHERE user_id = ? AND event_type = ?
                ORDER BY created_at DESC
                """,
                (token, event_type),
            )
        else:
            cursor.execute(
                """
                SELECT webhook_id, name, event_type, target_url, is_active,
                       created_at, last_triggered_at, trigger_count
                FROM webhook_subscriptions
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (token,),
            )

        rows = cursor.fetchall()
        webhooks = [
            WebhookSubscriptionResponse(
                webhook_id=row["webhook_id"],
                name=row["name"],
                event_type=row["event_type"],
                target_url=row["target_url"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                last_triggered_at=row["last_triggered_at"],
                trigger_count=row["trigger_count"],
            )
            for row in rows
        ]

        return WebhookListResponse(webhooks=webhooks, total=len(webhooks))

    finally:
        conn.close()
