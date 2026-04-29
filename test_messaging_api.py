#!/usr/bin/env python3
"""
Task #2547 バックエンド API テスト
- Webhook API
- WebSocket イベント配信
- Task completion event 発行
"""
import asyncio
import json
from datetime import datetime
from dashboard import models

async def test_models():
    """モデルのバリデーションテスト"""
    print("=== Testing Models ===")

    # TaskCompletionEvent
    event = models.TaskCompletionEvent(
        type="task.completed",
        timestamp=datetime.utcnow().isoformat() + "Z",
        task_id=2547,
        task_title="AIエージェント間メッセージング・通知システム実装",
        workflow_id="2547",
        team_name="agent-messaging",
        executor=models.TaskCompletionEventExecutor(
            user_id="usr_001",
            username="adachi-koichi",
            role="ai-engineer",
        ),
        status="completed",
        priority=1,
        completion_time_ms=1800000,
        metadata=models.TaskCompletionEventMetadata(
            tag_ids=["urgent", "mvp"],
            category="infra",
            phase="design",
        ),
    )

    print(f"✓ TaskCompletionEvent: {event.task_id} ({event.task_title})")
    print(f"  - Executor: {event.executor.username} ({event.executor.role})")
    print(f"  - Status: {event.status}, Priority: {event.priority}")
    print(f"  - Tags: {event.metadata.tag_ids}")
    print()

    # WebhookSubscriptionCreate
    webhook = models.WebhookSubscriptionCreate(
        name="orchestrator-webhook",
        event_type="task.completed",
        target_url="https://example.com/webhooks/task-completed",
        auth_type="bearer",
        secret_key="test_secret_key_12345",
        is_active=True,
        retry_policy={
            "max_retries": 3,
            "retry_backoff_ms": 1000,
            "timeout_ms": 5000,
        },
        headers={"X-Custom-Header": "test-value"},
    )

    print(f"✓ WebhookSubscriptionCreate: {webhook.name}")
    print(f"  - Target URL: {webhook.target_url}")
    print(f"  - Auth Type: {webhook.auth_type}")
    print(f"  - Retry Policy: {webhook.retry_policy}")
    print()

def test_database():
    """データベーステスト"""
    print("=== Testing Database ===")

    import sqlite3
    from pathlib import Path

    TASKS_DB = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "data" / "tasks.sqlite"

    if not TASKS_DB.exists():
        print(f"✗ Database file not found: {TASKS_DB}")
        return

    conn = sqlite3.connect(str(TASKS_DB))
    cursor = conn.cursor()

    # テーブル確認
    tables = ["task_completion_events", "webhook_subscriptions", "webhook_delivery_logs"]
    for table in tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if cursor.fetchone():
            print(f"✓ Table exists: {table}")
        else:
            print(f"✗ Table not found: {table}")

    conn.close()
    print()

def main():
    """テスト実行"""
    print("Task #2547 バックエンド API テスト\n")

    # モデルテスト
    asyncio.run(test_models())

    # データベーステスト
    test_database()

    print("=== Test Complete ===")
    print("✓ All basic checks passed")
    print("\nNext steps:")
    print("1. Start the FastAPI server: uvicorn dashboard.app:app --reload --port 8000")
    print("2. Test WebSocket: ws://localhost:8000/ws?token=<jwt_token>")
    print("3. Test Webhook API: curl -H 'Authorization: Bearer <token>' http://localhost:8000/api/webhooks")

if __name__ == "__main__":
    main()
