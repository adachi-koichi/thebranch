import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import secrets
import json
import base64
import io
from typing import Optional, Tuple

import aiosqlite
import pyotp
import qrcode

DB_PATH = Path.home() / ".claude" / "dashboard_auth.sqlite"


async def init_db():
    async with aiosqlite.connect(str(DB_PATH)) as db:
        migrations_dir = Path(__file__).parent / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))

        for migration_file in migration_files:
            sql = migration_file.read_text(encoding="utf-8")
            try:
                await db.executescript(sql)
                await db.commit()
            except sqlite3.OperationalError:
                pass


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
            cursor = await db.execute(
                "SELECT id FROM users WHERE username = ? AND org_id = ?",
                (username, org_id),
            )
            result = await cursor.fetchone()
            user_id = result[0] if result else None
            return True, "User created successfully", user_id
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
        expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
        now = datetime.utcnow().isoformat()

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
            (token, datetime.utcnow().isoformat()),
        )
        result = await cursor.fetchone()
        if result:
            return result[0], result[1]
        return None, None


async def update_last_activity(token: str) -> bool:
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            now = datetime.utcnow().isoformat()
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
            cutoff_time = (datetime.utcnow() - timedelta(minutes=timeout_minutes)).isoformat()
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
                (user_id, datetime.utcnow().isoformat()),
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


async def create_api_token(user_id: str, name: str, scope: str, expires_in_days: Optional[int] = None, org_id: str = "default") -> Tuple[bool, str, Optional[str]]:
    """
    パーソナルアクセストークンを生成します。

    Args:
        user_id: ユーザーID
        name: トークンの名前（例: GitHub Integration）
        scope: カンマ区切りのスコープ（read,write,admin）
        expires_in_days: 有効期限（日数）。Noneの場合は無期限
        org_id: 組織ID

    Returns:
        (成功フラグ, メッセージ, トークン)
    """
    try:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = None
        if expires_in_days:
            expires_at = (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat()

        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                """INSERT INTO api_tokens
                   (user_id, token_hash, name, scope, org_id, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, token_hash, name, scope, org_id, expires_at),
            )
            await db.commit()
            token_id = cursor.lastrowid
            return True, f"API token '{name}' created successfully", token
    except Exception as e:
        return False, str(e), None


async def revoke_api_token(user_id: str, token_id: str, org_id: str = "default") -> Tuple[bool, str]:
    """
    パーソナルアクセストークンを無効化します。

    Args:
        user_id: ユーザーID
        token_id: トークンID
        org_id: 組織ID

    Returns:
        (成功フラグ, メッセージ)
    """
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                """UPDATE api_tokens
                   SET revoked_at = ?
                   WHERE id = ? AND user_id = ? AND org_id = ? AND revoked_at IS NULL""",
                (datetime.utcnow().isoformat(), token_id, user_id, org_id),
            )
            await db.commit()

            if cursor.rowcount == 0:
                return False, "Token not found or already revoked"
            return True, "API token revoked successfully"
    except Exception as e:
        return False, str(e)


async def verify_api_token_scope(token: str, required_scope: str, org_id: str = "default") -> Tuple[Optional[str], Optional[str], bool]:
    """
    APIトークンを検証し、スコープをチェックします。

    Args:
        token: APIトークン（平文）
        required_scope: 必要なスコープ（read, write, admin）
        org_id: 組織ID

    Returns:
        (user_id, token_id, スコープチェック結果)
    """
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                """SELECT id, user_id, scope FROM api_tokens
                   WHERE token_hash = ? AND org_id = ? AND revoked_at IS NULL
                   AND (expires_at IS NULL OR expires_at > ?)""",
                (token_hash, org_id, datetime.utcnow().isoformat()),
            )
            result = await cursor.fetchone()

            if not result:
                return None, None, False

            token_id, user_id, token_scope = result
            scopes = set(s.strip() for s in token_scope.split(","))

            if "admin" in scopes:
                has_scope = True
            else:
                has_scope = required_scope in scopes

            await db.execute(
                "UPDATE api_tokens SET last_used_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), token_id),
            )
            await db.commit()

            return user_id, token_id, has_scope
    except Exception:
        return None, None, False


async def list_api_tokens(user_id: str, org_id: str = "default") -> list:
    """
    ユーザーのすべてのAPIトークンを一覧表示します。

    Args:
        user_id: ユーザーID
        org_id: 組織ID

    Returns:
        トークン情報のリスト
    """
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                """SELECT id, name, scope, created_at, last_used_at, expires_at, revoked_at
                   FROM api_tokens
                   WHERE user_id = ? AND org_id = ?
                   ORDER BY created_at DESC""",
                (user_id, org_id),
            )
            rows = await cursor.fetchall()

            tokens = []
            for row in rows:
                tokens.append({
                    "id": row[0],
                    "name": row[1],
                    "scope": row[2],
                    "created_at": row[3],
                    "last_used_at": row[4],
                    "expires_at": row[5],
                    "revoked": row[6] is not None,
                })
            return tokens
    except Exception:
        return []


async def enable_2fa(user_id: str) -> Tuple[str, str, list]:
    """
    TOTP 2FAを有効化し、秘密鍵、QRコード、バックアップコードを生成します。

    Args:
        user_id: ユーザーID

    Returns:
        (secret, qr_code_base64, backup_codes)
    """
    try:
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(name=user_id, issuer_name="THEBRANCH")

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_code_base64 = base64.b64encode(buf.getvalue()).decode()
        qr_code_data_uri = f"data:image/png;base64,{qr_code_base64}"

        backup_codes = [secrets.token_hex(4) for _ in range(10)]
        backup_codes_json = json.dumps(backup_codes)

        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                """INSERT INTO totp_secrets (user_id, secret, backup_codes, is_enabled)
                   VALUES (?, ?, ?, 0)
                   ON CONFLICT(user_id) DO UPDATE SET
                   secret = excluded.secret,
                   backup_codes = excluded.backup_codes,
                   is_enabled = 0""",
                (user_id, secret, backup_codes_json),
            )
            await db.commit()

        return secret, qr_code_data_uri, backup_codes
    except Exception as e:
        raise Exception(f"Failed to enable 2FA: {str(e)}")


async def verify_2fa_token(user_id: str, totp_code: str) -> Tuple[bool, str]:
    """
    TOTP トークンを検証し、2FAを有効化します。

    Args:
        user_id: ユーザーID
        totp_code: TOTP コード（6桁）

    Returns:
        (成功フラグ, メッセージ)
    """
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                "SELECT secret FROM totp_secrets WHERE user_id = ? AND is_enabled = 0",
                (user_id,),
            )
            result = await cursor.fetchone()

            if not result:
                return False, "2FA not initialized"

            secret = result[0]
            totp = pyotp.TOTP(secret)

            if not totp.verify(totp_code, valid_window=1):
                return False, "Invalid TOTP code"

            now = datetime.utcnow()
            cursor = await db.execute(
                """UPDATE totp_secrets
                   SET is_enabled = 1, enabled_at = ?
                   WHERE user_id = ?""",
                (now, user_id),
            )
            await db.commit()

            if cursor.rowcount == 0:
                return False, "Failed to enable 2FA"

            return True, "2FA enabled successfully"
    except Exception as e:
        return False, f"Failed to verify TOTP: {str(e)}"


async def disable_2fa(user_id: str, password: str) -> Tuple[bool, str]:
    """
    TOTP 2FAを無効化します（パスワード確認が必要）。

    Args:
        user_id: ユーザーID
        password: ユーザーのパスワード（確認用）

    Returns:
        (成功フラグ, メッセージ)
    """
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (user_id,),
            )
            result = await cursor.fetchone()

            if not result or not verify_password(password, result[0]):
                return False, "Invalid password"

            cursor = await db.execute(
                "DELETE FROM totp_secrets WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()

            if cursor.rowcount == 0:
                return False, "2FA not found for user"

            return True, "2FA disabled successfully"
    except Exception as e:
        return False, f"Failed to disable 2FA: {str(e)}"
