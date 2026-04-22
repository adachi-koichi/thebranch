#!/usr/bin/env python3
"""
Dashboard DB マイグレーション実行スクリプト

マイグレーションファイルを migrations/ ディレクトリから読み込み、
実行済みのマイグレーションを追跡しながら順番に実行します。
"""

import sqlite3
from pathlib import Path
import sys

DASHBOARD_DIR = Path(__file__).parent
MIGRATIONS_DIR = DASHBOARD_DIR / "migrations"
DB_PATH = DASHBOARD_DIR / "data" / "thebranch.sqlite"


def get_db_connection():
    """データベース接続を取得"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_migrations_table(conn):
    """マイグレーション追跡テーブルを初期化"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            executed_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()


def get_executed_migrations(conn):
    """実行済みのマイグレーション名を取得"""
    cursor = conn.execute("SELECT name FROM migrations ORDER BY name")
    return {row[0] for row in cursor.fetchall()}


def run_migration(conn, migration_file):
    """マイグレーションファイルを実行"""
    print(f"  実行中: {migration_file.name}...", end=" ")

    with open(migration_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    try:
        conn.executescript(sql_content)
        conn.commit()

        cursor = conn.execute(
            "INSERT INTO migrations (name) VALUES (?)",
            (migration_file.name,)
        )
        conn.commit()

        print("✓ 完了")
        return True
    except Exception as e:
        print(f"✗ エラー")
        print(f"    {str(e)}")
        conn.rollback()
        return False


def main():
    """メインマイグレーション実行処理"""
    # マイグレーションディレクトリの確認
    if not MIGRATIONS_DIR.exists():
        print(f"エラー: {MIGRATIONS_DIR} が見つかりません")
        sys.exit(1)

    # データベース接続
    conn = get_db_connection()

    try:
        # マイグレーション追跡テーブル初期化
        init_migrations_table(conn)

        # 実行済みマイグレーション取得
        executed = get_executed_migrations(conn)

        # マイグレーションファイル一覧を取得・ソート
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        if not migration_files:
            print("マイグレーションファイルが見つかりません")
            sys.exit(1)

        print(f"\n📦 マイグレーション実行開始 ({len(migration_files)} ファイル)")
        print(f"   データベース: {DB_PATH}\n")

        executed_count = 0
        failed_count = 0

        for migration_file in migration_files:
            if migration_file.name in executed:
                print(f"  スキップ: {migration_file.name} (既実行)")
                continue

            if run_migration(conn, migration_file):
                executed_count += 1
            else:
                failed_count += 1

        print(f"\n✅ マイグレーション完了")
        print(f"   新規実行: {executed_count}")
        print(f"   既実行: {len(executed)}")
        if failed_count > 0:
            print(f"   失敗: {failed_count}")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ マイグレーション実行エラー: {str(e)}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
