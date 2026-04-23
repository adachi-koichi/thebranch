#!/usr/bin/env python3
"""Run migration 023 - product design workflow templates"""
import sqlite3
from pathlib import Path

def main():
    db_path = Path(__file__).parent / "dashboard" / "data" / "thebranch.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Database: {db_path}")

    migration_file = Path(__file__).parent / "dashboard" / "migrations" / "023_product_design_workflow_templates.sql"

    if not migration_file.exists():
        print(f"✗ Migration file not found: {migration_file}")
        return False

    print(f"\nApplying migration: {migration_file.name}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        sql = migration_file.read_text(encoding="utf-8")
        cursor.executescript(sql)
        conn.commit()
        print(f"✓ Migration 023 applied successfully\n")

        # Verify templates were created
        cursor = conn.execute("SELECT id, name FROM workflow_templates ORDER BY id")
        templates = cursor.fetchall()
        print(f"Templates created: {len(templates)}")
        for template_id, name in templates:
            cursor = conn.execute("SELECT COUNT(*) FROM wf_template_phases WHERE template_id = ?", (template_id,))
            phase_count = cursor.fetchone()[0]
            cursor = conn.execute("SELECT COUNT(*) FROM wf_template_tasks WHERE template_id = ?", (template_id,))
            task_count = cursor.fetchone()[0]
            print(f"  [{template_id}] {name}: {phase_count} phases, {task_count} tasks")

        return True
    except Exception as e:
        print(f"✗ Error applying migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
