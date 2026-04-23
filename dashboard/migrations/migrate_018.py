#!/usr/bin/env python3
"""
Migration 018: Extend existing tables with team dynamics columns
This script extends agents, teams, and task_delegations tables with new columns
for team dynamics and optimization features.

Note: SQLite's ALTER TABLE ADD COLUMN IF NOT EXISTS requires SQLite 3.37.0+,
so this script provides Python-level existence checking for compatibility.
"""

import sqlite3
import sys
from pathlib import Path


def get_columns(cursor, table_name):
    """Get all column names for a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def main():
    # Determine database path
    migrations_dir = Path(__file__).parent
    db_path = migrations_dir.parent / "data" / "thebranch.sqlite"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # agents テーブル拡張
        agents_cols = get_columns(cursor, 'agents')
        agents_additions = [
            ('workload_level', 'INTEGER DEFAULT 0'),
            ('skill_tags', 'TEXT'),
            ('collaboration_score', 'REAL DEFAULT 50'),
            ('last_activity_at', 'TEXT'),
        ]

        for col_name, col_def in agents_additions:
            if col_name not in agents_cols:
                cursor.execute(f"ALTER TABLE agents ADD COLUMN {col_name} {col_def}")
                print(f"✓ agents.{col_name} added")
            else:
                print(f"⚠ agents.{col_name} already exists")

        # teams テーブル拡張
        teams_cols = get_columns(cursor, 'teams')
        teams_additions = [
            ('optimization_enabled', 'BOOLEAN DEFAULT 1'),
            ('performance_tier', "TEXT DEFAULT 'silver'"),
            ('sla_target_completion_rate', 'REAL DEFAULT 0.90'),
        ]

        for col_name, col_def in teams_additions:
            if col_name not in teams_cols:
                cursor.execute(f"ALTER TABLE teams ADD COLUMN {col_name} {col_def}")
                print(f"✓ teams.{col_name} added")
            else:
                print(f"⚠ teams.{col_name} already exists")

        # task_delegations テーブル拡張
        task_cols = get_columns(cursor, 'task_delegations')
        task_additions = [
            ('allocation_algorithm_used', 'TEXT'),
            ('allocation_score', 'REAL'),
            ('reallocation_reason', 'TEXT'),
        ]

        for col_name, col_def in task_additions:
            if col_name not in task_cols:
                cursor.execute(f"ALTER TABLE task_delegations ADD COLUMN {col_name} {col_def}")
                print(f"✓ task_delegations.{col_name} added")
            else:
                print(f"⚠ task_delegations.{col_name} already exists")

        conn.commit()
        print("\n✅ Migration 018 completed successfully")
        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
