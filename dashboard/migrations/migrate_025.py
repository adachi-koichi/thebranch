#!/usr/bin/env python3
"""Migration 025: Sessions テーブル拡張 (last_activity_at, ip_address, user_agent, is_forced_logout)"""

import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "dashboard_auth.sqlite"


def migrate():
    """セッション管理強化のためのマイグレーション"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # テーブル情報を取得
        cursor.execute("PRAGMA table_info(sessions)")
        columns = {row[1] for row in cursor.fetchall()}

        # 既存のカラムをチェック
        to_add = []
        if "last_activity_at" not in columns:
            to_add.append(("last_activity_at", "DATETIME"))
        if "ip_address" not in columns:
            to_add.append(("ip_address", "TEXT"))
        if "user_agent" not in columns:
            to_add.append(("user_agent", "TEXT"))
        if "is_forced_logout" not in columns:
            to_add.append(("is_forced_logout", "INTEGER DEFAULT 0"))

        # カラムを追加
        for col_name, col_type in to_add:
            cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}")
            print(f"✓ Added column: {col_name}")

        # インデックスを作成
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_is_forced_logout ON sessions(is_forced_logout)")
        print("✓ Created indexes")

        conn.commit()
        print("✓ Migration 025 completed")

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"⚠ Columns already exist: {e}")
            conn.rollback()
        else:
            raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
