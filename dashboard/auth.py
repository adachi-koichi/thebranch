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


async def create_user(username: str, email: str, password: str) -> Tuple[bool, str]:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            hashed = hash_password(password)
            await db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, hashed),
            )
            await db.commit()
            return True, "User created successfully"
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return False, "Username already exists"
        elif "email" in str(e):
            return False, "Email already exists"
        return False, str(e)
    except Exception as e:
        return False, str(e)


async def authenticate_user(username: str, password: str) -> Tuple[Optional[str], Optional[str]]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username,),
        )
        user = await cursor.fetchone()

        if not user or not verify_password(password, user[1]):
            return None, None

        user_id = user[0]
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=7)

        await db.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at),
        )
        await db.commit()

        return user_id, token


async def verify_token(token: str) -> Optional[str]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT user_id FROM sessions WHERE token = ? AND expires_at > ?",
            (token, datetime.utcnow()),
        )
        result = await cursor.fetchone()
        return result[0] if result else None


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
