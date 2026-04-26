#!/usr/bin/env python3
"""セキュリティ機能の E2E テスト: 複数機能の統合動作検証"""

import asyncio
import uuid
import json
from pathlib import Path
from dashboard import auth
import pyotp

DB_PATH = Path.home() / ".claude" / "dashboard_auth.sqlite"


async def e2e_scenario_1_complete_user_onboarding():
    """
    E2E シナリオ 1: 新規ユーザーのオンボーディングと2FA有効化

    ユーザーが新規登録し、2FAを有効化してセッションを確立する流れ
    """
    print("\n" + "=" * 60)
    print("E2E Scenario 1: Complete User Onboarding with 2FA")
    print("=" * 60)

    # 1. ユーザー登録
    username = f"e2e_onboard_{uuid.uuid4().hex[:8]}"
    email = f"e2e_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    success, msg, user_id = await auth.create_user(username, email, password)
    assert success, f"User creation failed: {msg}"
    print(f"[1] ✓ User registered: {user_id}")

    # 2. ユーザーがログイン（セッション作成）
    user_id, session_token, org_id = await auth.authenticate_user(username, password)
    assert session_token, "Login failed"
    print(f"[2] ✓ User logged in, session created")

    # 3. セッションを検証
    verified_user, verified_org = await auth.verify_token(session_token)
    assert verified_user == user_id, "Session verification failed"
    print(f"[3] ✓ Session verified")

    # 4. 2FA を初期化
    secret, qr_code_data_uri, backup_codes = await auth.enable_2fa(user_id)
    assert secret and backup_codes, "2FA initialization failed"
    print(f"[4] ✓ 2FA initialized with {len(backup_codes)} backup codes")

    # 5. TOTP コードで 2FA を有効化
    totp = pyotp.TOTP(secret)
    totp_code = totp.now()
    success, msg = await auth.verify_2fa_token(user_id, totp_code)
    assert success, f"2FA verification failed: {msg}"
    print(f"[5] ✓ 2FA enabled via TOTP verification")

    # 6. API トークンを生成（CI/CD integration）
    success, msg, api_token = await auth.create_api_token(user_id, "CI/CD Pipeline", "read,write", expires_in_days=365)
    assert api_token, f"API token creation failed: {msg}"
    print(f"[6] ✓ API token created for CI/CD integration")

    # 7. 最後のアクティビティを更新
    success = await auth.update_last_activity(session_token)
    assert success, "Failed to update activity"
    print(f"[7] ✓ Activity timestamp updated")

    # 8. ユーザーのアクティブセッションを確認
    sessions = await auth.list_active_sessions(user_id)
    assert len(sessions) >= 1, "No active sessions"
    print(f"[8] ✓ User has {len(sessions)} active session(s)")

    # 9. API トークンを検証
    verified_user, token_id, has_scope = await auth.verify_api_token_scope(api_token, "write")
    assert verified_user == user_id and has_scope, "API token verification failed"
    print(f"[9] ✓ API token verified with write scope")

    print("\n✓ Scenario 1 completed: User fully onboarded with 2FA and API token")


async def e2e_scenario_2_multi_session_device_management():
    """
    E2E シナリオ 2: 複数デバイスでのセッション管理

    ユーザーが複数デバイスからログインして、セッション数制限とデバイス管理をテストする
    """
    print("\n" + "=" * 60)
    print("E2E Scenario 2: Multi-Session Device Management")
    print("=" * 60)

    # 1. ユーザー登録
    username = f"e2e_multi_device_{uuid.uuid4().hex[:8]}"
    email = f"e2e_multi_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(username, email, "password123")
    assert success, f"User creation failed: {msg}"
    print(f"[1] ✓ User registered: {user_id}")

    # 2. デバイス 1 からログイン（Desktop）
    user_id, device1_token, org_id = await auth.authenticate_user(username, "password123")
    assert device1_token, "Device 1 login failed"
    print(f"[2] ✓ Device 1 (Desktop) logged in")

    # 3. デバイス 2 からログイン（Mobile）
    user_id, device2_token, org_id = await auth.authenticate_user(username, "password123")
    assert device2_token, "Device 2 login failed"
    print(f"[3] ✓ Device 2 (Mobile) logged in")

    # 4. デバイス 3 からログイン（Tablet）
    user_id, device3_token, org_id = await auth.authenticate_user(username, "password123")
    assert device3_token, "Device 3 login failed"
    print(f"[4] ✓ Device 3 (Tablet) logged in")

    # 5. すべてのセッションが有効
    verified_user1, _ = await auth.verify_token(device1_token)
    verified_user2, _ = await auth.verify_token(device2_token)
    verified_user3, _ = await auth.verify_token(device3_token)
    assert all([verified_user1, verified_user2, verified_user3]), "Some sessions failed verification"
    print(f"[5] ✓ All 3 device sessions verified")

    # 6. デバイス 4 からログイン（Laptop）- これで4つ目のセッション
    user_id, device4_token, org_id = await auth.authenticate_user(username, "password123")
    assert device4_token, "Device 4 login failed"
    print(f"[6] ✓ Device 4 (Laptop) logged in - 4 sessions created")

    # 7. セッション数制限を強制（最大3個）
    revoked = await auth.enforce_max_sessions(user_id, max_sessions=3)
    assert len(revoked) > 0, "Should have revoked sessions"
    print(f"[7] ✓ enforce_max_sessions: revoked {len(revoked)} session(s)")

    # 8. アクティブセッションを確認
    sessions = await auth.list_active_sessions(user_id)
    assert len(sessions) == 3, f"Expected 3 sessions, got {len(sessions)}"
    print(f"[8] ✓ Active sessions reduced to {len(sessions)} (limit enforced)")

    # 9. 最も古いセッション（device1）は無効になっているはず
    verified_user, _ = await auth.verify_token(device1_token)
    assert verified_user is None, "Oldest session (Device 1) should be revoked"
    print(f"[9] ✓ Oldest session (Device 1) correctly revoked")

    # 10. 新しいセッションはまだ有効（device4は最新なので有効）
    verified_user4, _ = await auth.verify_token(device4_token)
    assert verified_user4 == user_id, "Device 4 session should still be valid"
    print(f"[10] ✓ Recent sessions still valid (Device 4 is newest)")

    print("\n✓ Scenario 2 completed: Multi-device session management working correctly")


async def e2e_scenario_3_api_token_integration():
    """
    E2E シナリオ 3: API トークン統合シナリオ

    複数の API トークンを管理して、権限スコープを検証する
    """
    print("\n" + "=" * 60)
    print("E2E Scenario 3: API Token Integration")
    print("=" * 60)

    # 1. ユーザー登録
    username = f"e2e_api_integration_{uuid.uuid4().hex[:8]}"
    email = f"e2e_api_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(username, email, "password123")
    assert success, f"User creation failed: {msg}"
    print(f"[1] ✓ User registered: {user_id}")

    # 2. CI/CD 用 read-only トークン生成
    success, msg, ci_token = await auth.create_api_token(user_id, "CI/CD Read", "read", expires_in_days=365)
    assert ci_token, f"CI token creation failed: {msg}"
    print(f"[2] ✓ CI/CD read-only token created")

    # 3. Webhook 用 write トークン生成
    success, msg, webhook_token = await auth.create_api_token(user_id, "Webhook Writer", "write", expires_in_days=90)
    assert webhook_token, f"Webhook token creation failed: {msg}"
    print(f"[3] ✓ Webhook write token created")

    # 4. Admin 用 admin トークン生成
    success, msg, admin_token = await auth.create_api_token(user_id, "Admin Token", "admin", expires_in_days=365)
    assert admin_token, f"Admin token creation failed: {msg}"
    print(f"[4] ✓ Admin token created")

    # 5. CI/CD トークンの権限を検証
    uid, tid, has_read = await auth.verify_api_token_scope(ci_token, "read")
    assert uid == user_id and has_read, "CI token should have read scope"
    uid, tid, has_write = await auth.verify_api_token_scope(ci_token, "write")
    assert not has_write, "CI token should not have write scope"
    print(f"[5] ✓ CI token has read scope, no write scope")

    # 6. Webhook トークンの権限を検証
    uid, tid, has_write = await auth.verify_api_token_scope(webhook_token, "write")
    assert uid == user_id and has_write, "Webhook token should have write scope"
    uid, tid, has_read = await auth.verify_api_token_scope(webhook_token, "read")
    assert not has_read, "Webhook token should not have separate read scope"
    print(f"[6] ✓ Webhook token has write scope (exact match)")

    # 7. Admin トークンの権限を検証（すべてのスコープを持つ）
    uid, tid, has_admin = await auth.verify_api_token_scope(admin_token, "admin")
    assert uid == user_id and has_admin, "Admin token should have admin scope"
    uid, tid, has_read = await auth.verify_api_token_scope(admin_token, "read")
    assert has_read, "Admin token should have read scope"
    uid, tid, has_write = await auth.verify_api_token_scope(admin_token, "write")
    assert has_write, "Admin token should have write scope"
    print(f"[7] ✓ Admin token has all scopes (admin, read, write)")

    # 8. トークン一覧を確認
    tokens = await auth.list_api_tokens(user_id)
    assert len(tokens) == 3, f"Expected 3 tokens, got {len(tokens)}"
    print(f"[8] ✓ Token list shows {len(tokens)} tokens")

    # 9. Webhook トークンを無効化
    webhook_token_id = None
    for token in tokens:
        if token["name"] == "Webhook Writer":
            webhook_token_id = token["id"]
            break

    assert webhook_token_id, "Webhook token not found"
    success, msg = await auth.revoke_api_token(user_id, webhook_token_id)
    assert success, f"Failed to revoke webhook token: {msg}"
    print(f"[9] ✓ Webhook token revoked")

    # 10. 無効化されたトークンは使用不可
    uid, tid, has_write = await auth.verify_api_token_scope(webhook_token, "write")
    assert uid is None, "Revoked token should not verify"
    print(f"[10] ✓ Revoked token correctly rejected")

    # 11. 他のトークンはまだ有効
    uid, tid, has_read = await auth.verify_api_token_scope(ci_token, "read")
    assert uid == user_id, "CI token should still be valid"
    print(f"[11] ✓ Active tokens still working")

    print("\n✓ Scenario 3 completed: API token integration and access control verified")


async def e2e_scenario_4_session_timeout_management():
    """
    E2E シナリオ 4: セッションタイムアウト管理

    非アクティブなセッションが自動削除される流れをテストする
    """
    print("\n" + "=" * 60)
    print("E2E Scenario 4: Session Timeout Management")
    print("=" * 60)

    # 1. ユーザー登録
    username = f"e2e_timeout_{uuid.uuid4().hex[:8]}"
    email = f"e2e_timeout_{uuid.uuid4().hex[:8]}@example.com"

    success, msg, user_id = await auth.create_user(username, email, "password123")
    assert success, f"User creation failed: {msg}"
    print(f"[1] ✓ User registered: {user_id}")

    # 2. 複数セッションを作成
    tokens = []
    for i in range(3):
        user_id, token, org_id = await auth.authenticate_user(username, "password123")
        tokens.append(token)
        print(f"[2.{i+1}] ✓ Session {i+1} created")

    # 3. セッション 1 のアクティビティを更新（アクティブに保つ）
    await auth.update_last_activity(tokens[0])
    print(f"[3] ✓ Session 1 activity updated (active)")

    # 4. セッション 2, 3 はアクティビティ更新なし（放置）
    print(f"[4] ✓ Sessions 2 and 3 left inactive")

    # 5. すべてのセッションがアクティブ
    verified_user1, _ = await auth.verify_token(tokens[0])
    verified_user2, _ = await auth.verify_token(tokens[1])
    verified_user3, _ = await auth.verify_token(tokens[2])
    assert all([verified_user1, verified_user2, verified_user3]), "All sessions should be active"
    print(f"[5] ✓ All 3 sessions are active")

    # 6. タイムアウト処理を実行（timeout_minutes=0 でテスト）
    cleaned, expired_ids = await auth.session_timeout(timeout_minutes=0)
    print(f"[6] ✓ Session timeout check: cleaned {cleaned} inactive sessions")

    # 7. アクティブセッションを確認
    sessions = await auth.list_active_sessions(user_id)
    active_session_count = len(sessions)
    print(f"[7] ✓ Active sessions remaining: {active_session_count}")

    print("\n✓ Scenario 4 completed: Session timeout management verified")


async def e2e_scenario_5_comprehensive_security_flow():
    """
    E2E シナリオ 5: 総合セキュリティフロー

    新規ユーザーが登録してから API を使用するまでの完全なセキュリティフロー
    """
    print("\n" + "=" * 60)
    print("E2E Scenario 5: Comprehensive Security Flow")
    print("=" * 60)

    # 1. ユーザー登録
    username = f"e2e_comprehensive_{uuid.uuid4().hex[:8]}"
    email = f"e2e_comp_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"

    success, msg, user_id = await auth.create_user(username, email, password)
    assert success, f"User creation failed: {msg}"
    print(f"[1] ✓ User registered")

    # 2. ログイン（セッション作成）
    user_id, session_token, org_id = await auth.authenticate_user(username, password)
    assert session_token, "Login failed"
    print(f"[2] ✓ User logged in")

    # 3. 2FA 初期化
    secret, qr_code, backup_codes = await auth.enable_2fa(user_id)
    assert secret, "2FA init failed"
    print(f"[3] ✓ 2FA initialized")

    # 4. 2FA 有効化
    totp = pyotp.TOTP(secret)
    success, msg = await auth.verify_2fa_token(user_id, totp.now())
    assert success, f"2FA verification failed: {msg}"
    print(f"[4] ✓ 2FA enabled")

    # 5. API トークン生成（読み取り専用）
    success, msg, read_token = await auth.create_api_token(user_id, "Read Only", "read")
    assert read_token, f"Read token creation failed: {msg}"
    print(f"[5] ✓ Read-only API token created")

    # 6. API トークン生成（管理用）
    success, msg, admin_token = await auth.create_api_token(user_id, "Admin", "admin", expires_in_days=30)
    assert admin_token, f"Admin token creation failed: {msg}"
    print(f"[6] ✓ Admin API token created")

    # 7. セッションとトークンの同時検証
    verified_user, _ = await auth.verify_token(session_token)
    assert verified_user == user_id, "Session verification failed"
    verified_user, _, has_scope = await auth.verify_api_token_scope(read_token, "read")
    assert verified_user == user_id and has_scope, "Read token verification failed"
    verified_user, _, has_scope = await auth.verify_api_token_scope(admin_token, "admin")
    assert verified_user == user_id and has_scope, "Admin token verification failed"
    print(f"[7] ✓ Session and API tokens verified")

    # 8. 複数デバイスでログイン
    _, device2_token, _ = await auth.authenticate_user(username, password)
    assert device2_token, "Device 2 login failed"
    print(f"[8] ✓ Secondary device logged in")

    # 9. セッション数制限（最大2個に制限）
    await auth.enforce_max_sessions(user_id, max_sessions=2)
    sessions = await auth.list_active_sessions(user_id)
    assert len(sessions) <= 2, "Session limit not enforced"
    print(f"[9] ✓ Session limit enforced ({len(sessions)} sessions)")

    # 10. API トークン一覧を確認
    tokens = await auth.list_api_tokens(user_id)
    assert len(tokens) >= 2, "Should have at least 2 API tokens"
    print(f"[10] ✓ {len(tokens)} API tokens available")

    # 11. セッションをログアウト
    success, msg = await auth.logout_user(session_token)
    assert success, f"Logout failed: {msg}"
    print(f"[11] ✓ Session logged out")

    # 12. ログアウト後、セッションは無効
    verified_user, _ = await auth.verify_token(session_token)
    assert verified_user is None, "Logged out session should not verify"
    print(f"[12] ✓ Logged out session correctly rejected")

    # 13. しかし API トークンはまだ有効
    verified_user, _, has_scope = await auth.verify_api_token_scope(read_token, "read")
    assert verified_user == user_id and has_scope, "API token should still be valid"
    print(f"[13] ✓ API tokens still valid after session logout")

    print("\n✓ Scenario 5 completed: Comprehensive security flow verified")


async def main():
    """すべての E2E テストシナリオを実行"""
    try:
        await e2e_scenario_1_complete_user_onboarding()
        await e2e_scenario_2_multi_session_device_management()
        await e2e_scenario_3_api_token_integration()
        await e2e_scenario_4_session_timeout_management()
        await e2e_scenario_5_comprehensive_security_flow()

        print("\n" + "=" * 60)
        print("✓ All E2E test scenarios passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ E2E test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
