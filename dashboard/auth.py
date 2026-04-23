import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import secrets
from typing import Optional, Tuple

import aiosqlite

DB_PATH = Path.home() / ".claude" / "dashboard_auth.sqlite"


async def init_db():
    async with aiosqlite.connect(str(DB_PATH)) as db:
        migrations_path = Path(__file__).parent / "migrations" / "001_create_auth_tables.sql"
        sql = migrations_path.read_text(encoding="utf-8")
        await db.executescript(sql)
        await db.commit()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${hashed.hex()}"


def verify_password(password: str, hash_: str) -> bool:
    try:
        salt, hashed = hash_.split("$")
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return computed.hex() == hashed
    except ValueError:
        return False


async def create_user(username: str, email: str, password: str, org_id: str = "default") -> Tuple[bool, str, Optional[str]]:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            hashed = hash_password(password)
            cursor = await db.execute(
                "INSERT INTO users (username, email, password_hash, org_id) VALUES (?, ?, ?, ?)",
                (username, email, hashed, org_id),
            )
            await db.commit()
            user_id = cursor.lastrowid
            return True, "User created successfully", str(user_id)
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return False, "Username already exists", None
        elif "email" in str(e):
            return False, "Email already exists", None
        return False, str(e), None
    except Exception as e:
        return False, str(e), None


async def authenticate_user(username: str, password: str, org_id: str = "default") -> Tuple[Optional[str], Optional[str], Optional[str]]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT id, password_hash, org_id FROM users WHERE username = ? AND org_id = ?",
            (username, org_id),
        )
        user = await cursor.fetchone()

        if not user or not verify_password(password, user[1]):
            return None, None, None

        user_id = user[0]
        user_org_id = user[2]
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=7)
        now = datetime.utcnow()

        await db.execute(
            "INSERT INTO sessions (user_id, token, expires_at, org_id, last_activity_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, token, expires_at, user_org_id, now, now),
        )
        await db.commit()

        return user_id, token, user_org_id


async def verify_token(token: str) -> Tuple[Optional[str], Optional[str]]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT user_id, org_id FROM sessions WHERE token = ? AND expires_at > ? AND is_forced_logout = 0",
            (token, datetime.utcnow()),
        )
        result = await cursor.fetchone()
        if result:
            return result[0], result[1]
        return None, None


async def update_last_activity(token: str) -> bool:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            now = datetime.utcnow()
            cursor = await db.execute(
                "UPDATE sessions SET last_activity_at = ? WHERE token = ? AND is_forced_logout = 0",
                (now, token),
            )
            await db.commit()
            return cursor.rowcount > 0
    except Exception:
        return False


async def get_user_roles(user_id: str) -> list:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT role FROM user_roles WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def add_user_role(user_id: str, role: str) -> Tuple[bool, str]:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "INSERT INTO user_roles (user_id, role) VALUES (?, ?)",
                (user_id, role),
            )
            await db.commit()
            return True, "Role added successfully"
    except sqlite3.IntegrityError:
        return False, "User already has this role"
    except Exception as e:
        return False, str(e)


async def remove_user_role(user_id: str, role: str) -> Tuple[bool, str]:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                "DELETE FROM user_roles WHERE user_id = ? AND role = ?",
                (user_id, role),
            )
            await db.commit()
            if cursor.rowcount == 0:
                return False, "Role not found for user"
            return True, "Role removed successfully"
    except Exception as e:
        return False, str(e)


async def logout_user(token: str) -> Tuple[bool, str]:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE token = ?",
                (token,),
            )
            await db.commit()
            if cursor.rowcount == 0:
                return False, "Session not found"
            return True, "Logged out successfully"
    except Exception as e:
        return False, str(e)


async def session_timeout(timeout_minutes: int = 30) -> Tuple[int, list]:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            cursor = await db.execute(
                "SELECT id FROM sessions WHERE last_activity_at IS NOT NULL AND last_activity_at < ? AND is_forced_logout = 0",
                (cutoff_time,),
            )
            expired = await cursor.fetchall()
            expired_ids = [row[0] for row in expired]

            if expired_ids:
                placeholders = ",".join("?" * len(expired_ids))
                await db.execute(
                    f"DELETE FROM sessions WHERE id IN ({placeholders})",
                    expired_ids,
                )
                await db.commit()

            return len(expired_ids), expired_ids
    except Exception as e:
        return 0, []


async def enforce_max_sessions(user_id: str, max_sessions: int = 3) -> list:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                "SELECT id FROM sessions WHERE user_id = ? AND is_forced_logout = 0 ORDER BY created_at DESC",
                (user_id,),
            )
            sessions = await cursor.fetchall()

            revoked = []
            if len(sessions) > max_sessions:
                to_revoke = sessions[max_sessions:]
                revoke_ids = [row[0] for row in to_revoke]
                placeholders = ",".join("?" * len(revoke_ids))
                await db.execute(
                    f"UPDATE sessions SET is_forced_logout = 1 WHERE id IN ({placeholders})",
                    revoke_ids,
                )
                await db.commit()
                revoked = revoke_ids

            return revoked
    except Exception as e:
        return []


async def list_active_sessions(user_id: str) -> list:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                """SELECT id, ip_address, user_agent, created_at, last_activity_at, expires_at
                   FROM sessions WHERE user_id = ? AND is_forced_logout = 0 AND expires_at > ?
                   ORDER BY created_at DESC""",
                (user_id, datetime.utcnow()),
            )
            rows = await cursor.fetchall()

            sessions = []
            for row in rows:
                sessions.append({
                    "id": row[0],
                    "ip_address": row[1],
                    "user_agent": row[2],
                    "created_at": row[3],
                    "last_activity_at": row[4],
                    "expires_at": row[5],
                })

            return sessions
    except Exception as e:
        return []


async def force_logout_session(session_id: str) -> Tuple[bool, str]:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                "UPDATE sessions SET is_forced_logout = 1 WHERE id = ?",
                (session_id,),
            )
            await db.commit()

            if cursor.rowcount == 0:
                return False, "Session not found"
            return True, "Session terminated"
    except Exception as e:
        return False, str(e)
