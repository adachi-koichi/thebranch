#!/usr/bin/env python3
"""簡単なオンボーディング API テスト"""
import asyncio
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).parent))

from dashboard import app, auth, models
from fastapi.testclient import TestClient
import sqlite3

client = TestClient(app.app)


async def setup_test_user():
    """テストユーザーを作成して、有効なトークンを返す"""
    test_username = f"testuser-{uuid.uuid4().hex[:8]}"
    test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    test_password = "TestPassword123!"

    # ユーザー作成
    success, message = await auth.create_user(test_username, test_email, test_password)
    print(f"[Setup] ユーザー作成: {success} - {message}")

    # トークン生成（実際の認証）
    user_id, token = await auth.authenticate_user(test_username, test_password)
    print(f"[Setup] 認証: user_id={user_id}, token={token}")

    return user_id, token


async def test_onboarding_flow():
    """オンボーディング全フローのテスト"""

    # テストユーザーの作成
    test_user_id, test_token = await setup_test_user()

    print("=" * 60)
    print("オンボーディング API テスト")
    print("=" * 60)

    # Step 0: ビジョン入力
    vision = "営業チームを立ち上げたい"
    onboarding_id = str(uuid.uuid4())

    print(f"\n[Step 0] ビジョン入力")
    print(f"  - onboarding_id: {onboarding_id}")
    print(f"  - vision: {vision}")

    # Vision 保存
    resp_vision = client.post(
        "/api/onboarding/vision",
        json={"onboarding_id": onboarding_id, "vision_input": vision},
        headers={"Authorization": f"Bearer {test_token}"}
    )
    print(f"  - POST /api/onboarding/vision: {resp_vision.status_code}")
    if resp_vision.status_code != 201:
        print(f"    エラー: {resp_vision.json()}")
        return

    # テンプレート提案
    resp_suggest = client.post(
        "/api/onboarding/suggest",
        json={"onboarding_id": onboarding_id},
        headers={"Authorization": f"Bearer {test_token}"}
    )
    print(f"  - POST /api/onboarding/suggest: {resp_suggest.status_code}")
    if resp_suggest.status_code != 200:
        print(f"    エラー: {resp_suggest.json()}")
        return

    suggestions = resp_suggest.json()
    print(f"  - 提案数: {len(suggestions.get('suggestions', []))}")
    if not suggestions.get('suggestions'):
        print("    警告: 提案がありません")
        return

    selected_template = suggestions['suggestions'][0]
    print(f"  - 選択テンプレート: {selected_template['name']}")

    # Step 2: 詳細設定
    print(f"\n[Step 2] 詳細設定")

    resp_setup = client.post(
        "/api/onboarding/setup",
        json={
            "onboarding_id": onboarding_id,
            "template_id": selected_template['template_id'],
            "dept_name": "営業推進部",
            "manager_name": "田中太郎",
            "members_count": 3,
            "budget": 16500.0,
            "kpi": "月商1000万円達成"
        },
        headers={"Authorization": f"Bearer {test_token}"}
    )
    print(f"  - POST /api/onboarding/setup: {resp_setup.status_code}")
    if resp_setup.status_code != 200:
        print(f"    エラー: {resp_setup.json()}")
        return

    setup_data = resp_setup.json()
    print(f"  - 予算検証: {setup_data.get('budget_validation', {}).get('status')}")
    if 'initial_tasks' in setup_data:
        print(f"  - 初期タスク数: {len(setup_data['initial_tasks'])}")
    else:
        print(f"    警告: initial_tasks がレスポンスにありません")
        print(f"    実際のレスポンス: {json.dumps(setup_data, indent=2, ensure_ascii=False)}")
        return

    # Step 3: 実行
    print(f"\n[Step 3] 実行")

    resp_execute = client.post(
        "/api/onboarding/execute",
        json={
            "onboarding_id": onboarding_id,
            "template_id": selected_template['template_id'],
            "dept_name": "営業推進部"
        },
        headers={"Authorization": f"Bearer {test_token}"}
    )
    print(f"  - POST /api/onboarding/execute: {resp_execute.status_code}")
    if resp_execute.status_code != 200:
        print(f"    エラー: {resp_execute.json()}")
        return

    exec_data = resp_execute.json()
    print(f"  - 部署 ID: {exec_data.get('dept_id')}")
    print(f"  - エージェント状態: {exec_data.get('agent_status')}")
    print(f"  - ダッシュボード URL: {exec_data.get('dashboard_url')}")

    print("\n✓ 全フロー完了")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_onboarding_flow())
