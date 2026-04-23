#!/bin/bash

# Multi-tenant Authentication Endpoint Test Script
# Tests signup, login, logout, and token verification endpoints

BASE_URL="http://localhost:7002"

echo "=== Testing Multi-tenant Authentication Endpoints ==="
echo ""

# Test 1: User Signup
echo "1. Testing /auth/signup endpoint..."
SIGNUP_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "testuser@example.com",
    "password": "securepassword123",
    "org_id": "default"
  }')

echo "Response: $SIGNUP_RESPONSE"
USER_ID=$(echo "$SIGNUP_RESPONSE" | grep -o '"user_id":"[^"]*"' | cut -d'"' -f4)
echo "Extracted user_id: $USER_ID"
echo ""

# Test 2: User Login
echo "2. Testing /auth/login endpoint..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepassword123",
    "org_id": "default"
  }')

echo "Response: $LOGIN_RESPONSE"
TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
ORG_ID=$(echo "$LOGIN_RESPONSE" | grep -o '"org_id":"[^"]*"' | cut -d'"' -f4)
echo "Extracted token: $TOKEN"
echo "Extracted org_id: $ORG_ID"
echo ""

# Test 3: Token Verification
if [ -n "$TOKEN" ]; then
  echo "3. Testing /auth/verify endpoint..."
  VERIFY_RESPONSE=$(curl -s -X GET "$BASE_URL/auth/verify" \
    -H "Authorization: Bearer $TOKEN")

  echo "Response: $VERIFY_RESPONSE"
  echo ""
fi

# Test 4: User Logout
if [ -n "$TOKEN" ]; then
  echo "4. Testing /auth/logout endpoint..."
  LOGOUT_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/logout" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{}')

  echo "Response: $LOGOUT_RESPONSE"
  echo ""
fi

# Test 5: Verify token is invalid after logout
if [ -n "$TOKEN" ]; then
  echo "5. Testing token after logout (should fail)..."
  VERIFY_AFTER_LOGOUT=$(curl -s -X GET "$BASE_URL/auth/verify" \
    -H "Authorization: Bearer $TOKEN")

  echo "Response: $VERIFY_AFTER_LOGOUT"
  echo ""
fi

# Test 6: Signup with different org
echo "6. Testing signup with different org_id..."
SIGNUP_ORG_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "orguser",
    "email": "orguser@company.com",
    "password": "companypass123",
    "org_id": "company-org"
  }')

echo "Response: $SIGNUP_ORG_RESPONSE"
echo ""

echo "=== Test Complete ==="
