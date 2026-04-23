#!/usr/bin/env python3
"""API エンドポイント テスト"""

import asyncio
import uuid
from dashboard import auth

async def main():
    """セッションを作成してトークンを出力"""
    # テストユーザーを作成
    test_username = f"api_test_{uuid.uuid4().hex[:8]}"
    test_email = f"api_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(test_username, test_email, "password123")
    if success:
        print(f"User created: {user_id}")
    else:
        print(f"User creation: {msg}")

    # ユーザーをログイン（セッション作成）
    user_id, token, org_id = await auth.authenticate_user(test_username, "password123")
    if token:
        print(f"Token: {token}")
        print(f"User ID: {user_id}")

        # セッション一覧を取得してセッションIDを出力
        sessions = await auth.list_active_sessions(user_id)
        if sessions:
            session_id = sessions[0]["id"]
            print(f"Session ID: {session_id}")

if __name__ == "__main__":
    asyncio.run(main())
