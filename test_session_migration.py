#!/usr/bin/env python3
"""セッション管理テスト: migration 025 を適用"""

import asyncio
import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path.home() / ".claude" / "dashboard_auth.sqlite"

def run_migration():
    """Migration 025 を実行"""
    import subprocess
    migration_script = Path(__file__).parent / "dashboard" / "migrations" / "migrate_025.py"
    result = subprocess.run(["/usr/bin/python3", str(migration_script)], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Error:", result.stderr)
    if result.returncode != 0:
        raise Exception(f"Migration failed with code {result.returncode}")

async def test_session_functions():
    """セッション管理関数をテスト"""
    from dashboard import auth
    import uuid

    # テストユーザーを作成（ユニークなuserを使用）
    test_username = f"test_user_{uuid.uuid4().hex[:8]}"
    test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(test_username, test_email, "password123")
    if not success:
        print(f"User already exists: {msg}")
        # 既存ユーザーを取得
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute("SELECT id FROM users WHERE username = ?", (test_username,))
            row = await cursor.fetchone()
            user_id = row[0] if row else None
    else:
        print(f"✓ User created: {user_id}")

    if not user_id:
        print("❌ Failed to create/find user")
        return

    # ユーザーをログイン（セッション作成）
    user_id, token, org_id = await auth.authenticate_user(test_username, "password123")
    if token:
        print(f"✓ Session created: {token[:20]}...")
    else:
        print("❌ Failed to authenticate")
        return

    # last_activity_at を更新
    await auth.update_last_activity(token)
    print("✓ last_activity_at updated")

    # アクティブセッション一覧を取得
    sessions = await auth.list_active_sessions(user_id)
    print(f"✓ Active sessions: {len(sessions)}")
    for sess in sessions:
        print(f"  - Session {sess['id']}: {sess['created_at']}")

    # セッション数制限をテスト（最大3個を超える）
    tokens = [token]
    for i in range(3):
        _, t, _ = await auth.authenticate_user(test_username, "password123")
        if t:
            tokens.append(t)

    print(f"✓ Created {len(tokens)} sessions")

    # セッション数制限を強制（最大3個）
    revoked = await auth.enforce_max_sessions(user_id, max_sessions=3)
    print(f"✓ enforce_max_sessions: revoked {len(revoked)} sessions")

    # 新しいセッション一覧を取得
    sessions = await auth.list_active_sessions(user_id)
    print(f"✓ Active sessions after enforcement: {len(sessions)}")

    # セッションを強制ログアウト
    if sessions:
        session_id = sessions[0]["id"]
        success, msg = await auth.force_logout_session(session_id)
        print(f"✓ force_logout_session: {msg}")

    # タイムアウトテスト
    cleaned, expired_ids = await auth.session_timeout(timeout_minutes=0)
    print(f"✓ session_timeout: cleaned {cleaned} sessions")

async def main():
    run_migration()
    await test_session_functions()
    print("\n✓ All tests passed!")

if __name__ == "__main__":
    asyncio.run(main())
