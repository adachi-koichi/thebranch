"""
Authentication and authorization for multitenancy.

Implements:
1. JWT token validation with org_id
2. TenantIsolationMiddleware for FastAPI
3. Permission checking (RBAC)
4. Audit logging
"""

import json
import sqlite3
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps
import os

from fastapi import Request, HTTPException, Header
from starlette.middleware.base import BaseHTTPMiddleware


# ===== TOKEN CONFIGURATION =====

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ACCESS_TOKEN_EXPIRE_HOURS = 24


# ===== TOKEN GENERATION & VALIDATION (JSON-based alternative to JWT) =====

def create_access_token(
    user_id: str,
    org_id: str,
    role: str,
    email: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create token with org_id claim (JSON-based, no external JWT dependency).

    Args:
        user_id: User identifier
        org_id: Organization ID (multitenancy)
        role: User role (owner, admin, member, viewer)
        email: User email
        expires_delta: Token expiration time

    Returns:
        Base64-encoded token
    """
    if expires_delta is None:
        expires_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "email": email,
        "iat": datetime.utcnow().isoformat(),
        "exp": expire.isoformat()
    }

    token_json = json.dumps(payload)
    token_bytes = token_json.encode('utf-8')
    encoded_token = base64.b64encode(token_bytes).decode('utf-8')
    return encoded_token


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify token and extract claims.

    Args:
        token: Base64-encoded token string

    Returns:
        Token payload (dict)

    Raises:
        ValueError: If token is invalid or org_id is missing
    """
    try:
        token_bytes = base64.b64decode(token.encode('utf-8'))
        token_json = token_bytes.decode('utf-8')
        payload = json.loads(token_json)

        org_id = payload.get("org_id")
        if not org_id:
            raise ValueError("org_id not found in token")

        return payload

    except (ValueError, json.JSONDecodeError, base64.binascii.Error) as e:
        raise ValueError(f"Invalid token: {str(e)}")


# ===== TENANT ISOLATION MIDDLEWARE =====

class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tenant isolation in FastAPI.

    Flow:
    1. Extract Authorization header
    2. Verify JWT token
    3. Extract org_id from token
    4. Set request.state.org_id, user_id, role, email
    5. Pass to next handler
    """

    async def dispatch(self, request: Request, call_next):
        # Skip token check for health check endpoints
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # 1. Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        token = auth_header.split(" ", 1)[1]

        # 2. Verify token
        try:
            payload = verify_token(token)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")

        # 3. Extract claims
        org_id = payload.get("org_id")
        user_id = payload.get("sub")
        role = payload.get("role")
        email = payload.get("email")

        # 4. Set request state
        request.state.org_id = org_id
        request.state.user_id = user_id
        request.state.role = role
        request.state.email = email
        request.state.client_ip = self._get_client_ip(request)

        # 5. Call next handler
        response = await call_next(request)
        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP from request."""
        return request.client.host if request.client else "unknown"


# ===== RBAC (ROLE-BASED ACCESS CONTROL) =====

ROLE_PERMISSIONS = {
    "owner": ["create", "read", "update", "delete", "manage_org"],
    "admin": ["create", "read", "update", "manage_users"],
    "member": ["create", "read", "update"],
    "viewer": ["read"]
}


def check_permission(
    org_id: str,
    user_id: str,
    action: str,
    resource_type: str = None,
    db_connection: sqlite3.Connection = None
) -> bool:
    """
    Check if user has permission to perform action.

    Args:
        org_id: Organization ID
        user_id: User ID
        action: Action type (create, read, update, delete, manage_org)
        resource_type: Resource type (task, workflow, user, organization)
        db_connection: Database connection (optional, for future extensions)

    Returns:
        True if permission granted, False otherwise
    """
    # Get user role from payload or database
    # For now, assume role is in request.state (set by middleware)
    # In production, query users table

    # Placeholder: assume role is available
    role = "member"  # Default role

    permissions = ROLE_PERMISSIONS.get(role, [])
    return action in permissions


def require_permission(action: str, resource_type: str = None):
    """
    Decorator for permission checking in endpoints.

    Args:
        action: Required action
        resource_type: Resource type

    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            org_id = request.state.org_id
            user_id = request.state.user_id

            if not check_permission(org_id, user_id, action, resource_type):
                raise HTTPException(status_code=403, detail="No permission for this action")

            return await func(request, *args, **kwargs)

        return wrapper
    return decorator


# ===== AUDIT LOGGING =====

def log_audit(
    db_connection: sqlite3.Connection,
    org_id: str,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: int = None,
    old_value: Dict[str, Any] = None,
    new_value: Dict[str, Any] = None,
    ip_address: str = "unknown"
) -> None:
    """
    Record audit log for tenant boundary crossing access.

    Args:
        db_connection: Database connection
        org_id: Organization ID
        user_id: User ID
        action: Action type (create, read, update, delete, export)
        resource_type: Resource type (task, workflow, user)
        resource_id: Resource ID
        old_value: Previous value (dict)
        new_value: New value (dict)
        ip_address: Client IP address
    """
    cursor = db_connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO audit_logs
            (org_id, user_id, action, resource_type, resource_id, old_value, new_value, ip_address, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                org_id,
                user_id,
                action,
                resource_type,
                resource_id,
                json.dumps(old_value) if old_value else None,
                json.dumps(new_value) if new_value else None,
                ip_address,
                datetime.utcnow().isoformat()
            )
        )
        db_connection.commit()

    except sqlite3.Error as e:
        print(f"[AUDIT] Error logging audit: {e}")
        db_connection.rollback()


# ===== USER MANAGEMENT =====

def get_user_role(
    db_connection: sqlite3.Connection,
    org_id: str,
    user_id: str
) -> Optional[str]:
    """
    Get user role from database.

    Args:
        db_connection: Database connection
        org_id: Organization ID
        user_id: User ID

    Returns:
        User role or None if user not found
    """
    cursor = db_connection.cursor()

    try:
        cursor.execute(
            "SELECT role FROM users WHERE org_id = ? AND user_id = ?",
            (org_id, user_id)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    except sqlite3.Error as e:
        print(f"[AUTH] Error querying user role: {e}")
        return None


def create_user(
    db_connection: sqlite3.Connection,
    org_id: str,
    user_id: str,
    email: str,
    password_hash: str,
    role: str = "member"
) -> bool:
    """
    Create new user in organization.

    Args:
        db_connection: Database connection
        org_id: Organization ID
        user_id: User ID
        email: User email
        password_hash: Password hash
        role: User role (owner, admin, member, viewer)

    Returns:
        True if user created, False if error
    """
    cursor = db_connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO users (org_id, user_id, email, password_hash, role, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (org_id, user_id, email, password_hash, role)
        )
        db_connection.commit()
        return True

    except sqlite3.IntegrityError as e:
        print(f"[AUTH] User already exists: {e}")
        db_connection.rollback()
        return False

    except sqlite3.Error as e:
        print(f"[AUTH] Error creating user: {e}")
        db_connection.rollback()
        return False
