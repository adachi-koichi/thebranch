#!/usr/bin/env python3
"""セキュリティ機能の統合テスト: API Token、Session、2FA"""

import asyncio
import uuid
import json
from pathlib import Path
from datetime import datetime, timedelta
from dashboard import auth

DB_PATH = Path.home() / ".claude" / "dashboard_auth.sqlite"


async def test_api_token_lifecycle():
    """API トークンのライフサイクル管理テスト"""
    print("\n=== API Token Lifecycle Test ===")

    # テストユーザーを作成
    test_username = f"api_test_{uuid.uuid4().hex[:8]}"
    test_email = f"api_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(test_username, test_email, "password123")
    assert success, f"Failed to create user: {msg}"
    assert user_id, "User ID is None"
    print(f"✓ User created: {user_id}")

    # API トークンを生成
    success, msg, token = await auth.create_api_token(user_id, "Test Token 1", "read,write", expires_in_days=30)
    assert success, f"Failed to create API token: {msg}"
    assert token, "Token is None"
    print(f"✓ API token created: {token[:20]}...")

    # トークンを検証（read スコープ）
    uid, token_id, has_scope = await auth.verify_api_token_scope(token, "read")
    assert uid == user_id, "User ID mismatch"
    assert has_scope, "Read scope verification failed"
    print(f"✓ Token verified with read scope")

    # トークンを検証（write スコープ）
    uid, token_id, has_scope = await auth.verify_api_token_scope(token, "write")
    assert has_scope, "Write scope verification failed"
    print(f"✓ Token verified with write scope")

    # トークンを検証（存在しないスコープ）
    uid, token_id, has_scope = await auth.verify_api_token_scope(token, "admin")
    assert not has_scope, "Admin scope should not be granted"
    print(f"✓ Admin scope correctly denied")

    # トークン一覧を取得
    tokens = await auth.list_api_tokens(user_id)
    assert len(tokens) >= 1, "Token list should contain at least 1 token"
    assert tokens[0]["name"] == "Test Token 1", "Token name mismatch"
    assert not tokens[0]["revoked"], "Token should not be revoked"
    print(f"✓ Token listed: {tokens[0]['name']}")

    # トークンを無効化
    token_id = tokens[0]["id"]
    success, msg = await auth.revoke_api_token(user_id, token_id)
    assert success, f"Failed to revoke token: {msg}"
    print(f"✓ Token revoked: {token_id}")

    # 無効化されたトークンを検証（失敗するはず）
    uid, tid, has_scope = await auth.verify_api_token_scope(token, "read")
    assert uid is None, "Revoked token should not verify"
    print(f"✓ Revoked token correctly rejected")


async def test_session_management():
    """セッション管理のテスト"""
    print("\n=== Session Management Test ===")

    # テストユーザーを作成
    test_username = f"sess_test_{uuid.uuid4().hex[:8]}"
    test_email = f"sess_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(test_username, test_email, "password123")
    assert success, f"Failed to create user: {msg}"
    print(f"✓ User created: {user_id}")

    # ログイン（セッション作成）
    user_id, token, org_id = await auth.authenticate_user(test_username, "password123")
    assert user_id, "Login failed"
    assert token, "Token is None"
    print(f"✓ Session created: {token[:20]}...")

    # token を検証
    verified_user, verified_org = await auth.verify_token(token)
    assert verified_user == user_id, "User ID mismatch in verify_token"
    assert verified_org == "default", "Org ID mismatch"
    print(f"✓ Token verified")

    # last_activity_at を更新
    success = await auth.update_last_activity(token)
    assert success, "Failed to update last_activity_at"
    print(f"✓ last_activity_at updated")

    # アクティブセッション一覧を取得
    sessions = await auth.list_active_sessions(user_id)
    assert len(sessions) >= 1, "Should have at least 1 session"
    print(f"✓ {len(sessions)} active session(s)")

    # セッション数制限をテスト
    tokens = [token]
    for i in range(4):
        _, t, _ = await auth.authenticate_user(test_username, "password123")
        if t:
            tokens.append(t)

    print(f"✓ Created {len(tokens)} sessions")

    # 最大セッション数を強制（3個に制限）
    revoked = await auth.enforce_max_sessions(user_id, max_sessions=3)
    assert len(revoked) > 0, "Should have revoked some sessions"
    print(f"✓ enforce_max_sessions: revoked {len(revoked)} sessions")

    # 新しいセッション一覧を取得
    sessions = await auth.list_active_sessions(user_id)
    assert len(sessions) <= 3, f"Should have max 3 sessions, got {len(sessions)}"
    print(f"✓ After enforcement: {len(sessions)} active session(s)")

    # セッションを強制ログアウト
    if sessions:
        session_id = sessions[0]["id"]
        success, msg = await auth.force_logout_session(session_id)
        assert success, f"Failed to logout session: {msg}"
        print(f"✓ Session forcefully logged out")

    # タイムアウトテスト
    cleaned, expired_ids = await auth.session_timeout(timeout_minutes=0)
    print(f"✓ session_timeout: cleaned {cleaned} sessions")


async def test_2fa_workflow():
    """2FA（TOTP）ワークフローのテスト"""
    print("\n=== 2FA/TOTP Workflow Test ===")

    # テストユーザーを作成
    test_username = f"2fa_test_{uuid.uuid4().hex[:8]}"
    test_email = f"2fa_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(test_username, test_email, "password123")
    assert success, f"Failed to create user: {msg}"
    print(f"✓ User created: {user_id}")

    # 2FA を初期化
    secret, qr_code_data_uri, backup_codes = await auth.enable_2fa(user_id)
    assert secret, "Secret is None"
    assert qr_code_data_uri, "QR code data URI is None"
    assert len(backup_codes) == 10, f"Should have 10 backup codes, got {len(backup_codes)}"
    print(f"✓ 2FA initialized")
    print(f"  - Secret: {secret}")
    print(f"  - Backup codes: {len(backup_codes)}")
    print(f"  - QR code data URI length: {len(qr_code_data_uri)}")

    # TOTP コードを生成して検証
    import pyotp
    totp = pyotp.TOTP(secret)
    totp_code = totp.now()
    print(f"  - Generated TOTP code: {totp_code}")

    success, msg = await auth.verify_2fa_token(user_id, totp_code)
    assert success, f"Failed to verify 2FA: {msg}"
    print(f"✓ 2FA verified and enabled")

    # 2FA を無効化
    success, msg = await auth.disable_2fa(user_id, "password123")
    assert success, f"Failed to disable 2FA: {msg}"
    print(f"✓ 2FA disabled")


async def test_api_token_with_different_scopes():
    """異なるスコープの API トークンテスト"""
    print("\n=== API Token Scope Management Test ===")

    test_username = f"scope_test_{uuid.uuid4().hex[:8]}"
    test_email = f"scope_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(test_username, test_email, "password123")
    assert success, f"Failed to create user: {msg}"
    print(f"✓ User created: {user_id}")

    # read-only トークンを生成
    success, msg, read_token = await auth.create_api_token(user_id, "Read Token", "read", expires_in_days=7)
    assert success, f"Failed to create read token: {msg}"
    print(f"✓ Read-only token created")

    # admin トークンを生成
    success, msg, admin_token = await auth.create_api_token(user_id, "Admin Token", "admin", expires_in_days=90)
    assert success, f"Failed to create admin token: {msg}"
    print(f"✓ Admin token created")

    # read トークンの検証
    uid, tid, has_read = await auth.verify_api_token_scope(read_token, "read")
    assert has_read, "Read token should have read scope"
    uid, tid, has_write = await auth.verify_api_token_scope(read_token, "write")
    assert not has_write, "Read token should not have write scope"
    print(f"✓ Read token scope verified")

    # admin トークンの検証（admin はすべてのスコープを持つ）
    uid, tid, has_read = await auth.verify_api_token_scope(admin_token, "read")
    assert has_read, "Admin token should have read scope"
    uid, tid, has_write = await auth.verify_api_token_scope(admin_token, "write")
    assert has_write, "Admin token should have write scope"
    uid, tid, has_admin = await auth.verify_api_token_scope(admin_token, "admin")
    assert has_admin, "Admin token should have admin scope"
    print(f"✓ Admin token scope verified")

    # トークン一覧を確認
    tokens = await auth.list_api_tokens(user_id)
    assert len(tokens) >= 2, "Should have at least 2 tokens"
    print(f"✓ Token list: {len(tokens)} tokens")


async def test_session_token_independence():
    """セッショントークンと API トークンの独立性テスト"""
    print("\n=== Session and API Token Independence Test ===")

    test_username = f"indep_test_{uuid.uuid4().hex[:8]}"
    test_email = f"indep_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(test_username, test_email, "password123")
    assert success, f"Failed to create user: {msg}"
    print(f"✓ User created: {user_id}")

    # セッショントークンを生成
    user_id, session_token, org_id = await auth.authenticate_user(test_username, "password123")
    assert session_token, "Session token is None"
    print(f"✓ Session token created")

    # API トークンを生成
    success, msg, api_token = await auth.create_api_token(user_id, "Test API Token", "read", expires_in_days=30)
    assert success, f"Failed to create API token: {msg}"
    print(f"✓ API token created")

    # セッショントークンで verify_token
    verified_user, verified_org = await auth.verify_token(session_token)
    assert verified_user == user_id, "Session token verification failed"
    print(f"✓ Session token verified")

    # API トークンで verify_api_token_scope
    verified_user, token_id, has_scope = await auth.verify_api_token_scope(api_token, "read")
    assert verified_user == user_id, "API token verification failed"
    assert has_scope, "API token scope verification failed"
    print(f"✓ API token verified")

    # セッショントークンを無効化しても API トークンは有効
    await auth.logout_user(session_token)
    print(f"✓ Session token revoked")

    verified_user, verified_org = await auth.verify_token(session_token)
    assert verified_user is None, "Revoked session token should not verify"
    print(f"✓ Session token correctly revoked")

    # API トークンはまだ有効
    verified_user, token_id, has_scope = await auth.verify_api_token_scope(api_token, "read")
    assert verified_user == user_id, "API token should still be valid"
    print(f"✓ API token still valid after session revocation")


async def main():
    """すべての統合テストを実行"""
    try:
        await test_api_token_lifecycle()
        await test_session_management()
        await test_2fa_workflow()
        await test_api_token_with_different_scopes()
        await test_session_token_independence()

        print("\n" + "=" * 50)
        print("✓ All integration tests passed!")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
