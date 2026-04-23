#!/usr/bin/env python3
"""Unit tests for authentication endpoints."""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from dashboard import auth


async def test_auth_flow():
    """Test the complete authentication flow."""
    import uuid

    print("=== Authentication Unit Tests ===\n")

    # Generate unique usernames
    test_username = f"testuser_{uuid.uuid4().hex[:8]}"
    org_username = f"orguser_{uuid.uuid4().hex[:8]}"
    test_email = f"{test_username}@example.com"
    org_email = f"{org_username}@company.com"

    # Test 1: Create user
    print("1. Testing user creation...")
    success, message, user_id = await auth.create_user(
        test_username, test_email, "password123", "default"
    )
    assert success, f"Failed to create user: {message}"
    assert user_id, f"User ID not returned"
    print(f"✓ User created: {user_id}")
    print(f"  Message: {message}\n")

    # Test 2: Authenticate user
    print("2. Testing user authentication...")
    user_id_auth, token, org_id = await auth.authenticate_user(
        test_username, "password123", "default"
    )
    assert user_id_auth, "Authentication failed"
    assert token, "Token not generated"
    assert org_id == "default", f"org_id not correct: {org_id}"
    print(f"✓ User authenticated: {user_id_auth}")
    print(f"  Token: {token[:32]}...")
    print(f"  org_id: {org_id}\n")

    # Test 3: Verify token
    print("3. Testing token verification...")
    user_id_verify, org_id_verify = await auth.verify_token(token)
    assert user_id_verify, "Token verification failed"
    assert org_id_verify == "default", f"org_id not correct: {org_id_verify}"
    print(f"✓ Token verified: {user_id_verify}")
    print(f"  org_id: {org_id_verify}\n")

    # Test 4: Logout user
    print("4. Testing user logout...")
    success_logout, message_logout = await auth.logout_user(token)
    assert success_logout, f"Logout failed: {message_logout}"
    print(f"✓ User logged out")
    print(f"  Message: {message_logout}\n")

    # Test 5: Verify token is invalid after logout
    print("5. Testing token after logout (should fail)...")
    user_id_invalid, org_id_invalid = await auth.verify_token(token)
    assert not user_id_invalid, "Token should be invalid after logout"
    print(f"✓ Token is now invalid (as expected)\n")

    # Test 6: Test wrong password
    print("6. Testing authentication with wrong password...")
    user_id_wrong, token_wrong, org_id_wrong = await auth.authenticate_user(
        test_username, "wrongpassword", "default"
    )
    assert not user_id_wrong, "Should fail with wrong password"
    assert not token_wrong, "Should not generate token"
    print(f"✓ Authentication rejected (as expected)\n")

    # Test 7: Test multi-tenant isolation
    print("7. Testing multi-tenant isolation...")
    # Create user in different org
    success_org, message_org, user_id_org = await auth.create_user(
        org_username, org_email, "password123", "company-org"
    )
    assert success_org, f"Failed to create org user: {message_org}"
    print(f"✓ User created in company-org: {user_id_org}")

    # Try to authenticate with wrong org
    user_id_wrong_org, token_wrong_org, org_id_wrong_org = await auth.authenticate_user(
        org_username, "password123", "default"  # Wrong org
    )
    assert not user_id_wrong_org, "Should fail with wrong org"
    print(f"✓ Multi-tenant isolation works (auth failed for wrong org)\n")

    # Authenticate with correct org
    user_id_correct_org, token_correct_org, org_id_correct_org = await auth.authenticate_user(
        org_username, "password123", "company-org"
    )
    assert user_id_correct_org, "Should succeed with correct org"
    assert org_id_correct_org == "company-org"
    print(f"✓ User authenticated with correct org: {org_id_correct_org}\n")

    print("=== All Tests Passed ===")


if __name__ == "__main__":
    asyncio.run(test_auth_flow())
