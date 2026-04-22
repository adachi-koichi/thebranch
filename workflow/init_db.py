#!/usr/bin/env python3
"""Initialize database schema and seed initial data."""

import sqlite3
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_schema import initialize_schema
from seed_department_templates import seed_department_templates

def main():
    db_path = Path(__file__).parent.parent / "dashboard" / "instance" / "tasks.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INIT] Initializing database at: {db_path}\n")

    # Initialize schema
    conn = sqlite3.connect(str(db_path))
    try:
        print("[INIT] Creating schema...")
        initialize_schema(conn)
        print("[INIT] Schema initialized successfully!\n")
    finally:
        conn.close()

    # Seed initial data
    print("[INIT] Seeding department templates...")
    seed_department_templates(str(db_path))
    print("\n[INIT] Database initialization complete!")

if __name__ == "__main__":
    main()
