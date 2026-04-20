"""
Database migration scripts for multitenancy support.

Phase 1: Schema expansion
- Create organizations table
- Create users table
- Create audit_logs table
- Add org_id column to existing tables
- Create indexes
"""

import sqlite3
from pathlib import Path
from datetime import datetime


# ===== PHASE 1: CREATE NEW TABLES =====

CREATE_ORGANIZATIONS = """
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    tier TEXT CHECK(tier IN ('free', 'pro', 'enterprise')) DEFAULT 'free',
    status TEXT CHECK(status IN ('active', 'suspended', 'deleted')) DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    billing_email TEXT,
    metadata TEXT
);
"""

CREATE_ORGANIZATIONS_INDEXES = [
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_org_id ON organizations(org_id);""",
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);""",
]

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    email TEXT NOT NULL,
    password_hash TEXT,
    role TEXT CHECK(role IN ('owner', 'admin', 'member', 'viewer')) DEFAULT 'member',
    status TEXT CHECK(status IN ('active', 'inactive', 'invited', 'deleted')) DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TEXT,
    FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE,
    UNIQUE(org_id, email)
);
"""

CREATE_USERS_INDEXES = [
    """CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);""",
    """CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);""",
    """CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);""",
]

CREATE_AUDIT_LOGS = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id TEXT NOT NULL,
    user_id TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    ip_address TEXT,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE
);
"""

CREATE_AUDIT_LOGS_INDEXES = [
    """CREATE INDEX IF NOT EXISTS idx_audit_logs_org_id ON audit_logs(org_id);""",
    """CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);""",
]

# ===== PHASE 1: ALTER EXISTING TABLES =====

# Add org_id to workflow_templates
ADD_ORG_ID_WORKFLOW_TEMPLATES = """
ALTER TABLE workflow_templates ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
"""

CREATE_IDX_WORKFLOW_TEMPLATES_ORG = """
CREATE INDEX IF NOT EXISTS idx_workflow_templates_org_id ON workflow_templates(org_id);
"""

CREATE_IDX_WORKFLOW_TEMPLATES_ORG_NAME = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_templates_org_name
ON workflow_templates(org_id, name);
"""

# Add org_id to wf_template_phases
ADD_ORG_ID_WF_TEMPLATE_PHASES = """
ALTER TABLE wf_template_phases ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
"""

CREATE_IDX_WF_TEMPLATE_PHASES_ORG = """
CREATE INDEX IF NOT EXISTS idx_wf_template_phases_org_id ON wf_template_phases(org_id);
"""

# Add org_id to wf_template_tasks
ADD_ORG_ID_WF_TEMPLATE_TASKS = """
ALTER TABLE wf_template_tasks ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
"""

CREATE_IDX_WF_TEMPLATE_TASKS_ORG = """
CREATE INDEX IF NOT EXISTS idx_wf_template_tasks_org_id ON wf_template_tasks(org_id);
"""

# Add org_id to agents
ADD_ORG_ID_AGENTS = """
ALTER TABLE agents ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
"""

CREATE_IDX_AGENTS_ORG = """
CREATE INDEX IF NOT EXISTS idx_agents_org_id ON agents(org_id);
"""

# Add org_id to workflow_instances
ADD_ORG_ID_WORKFLOW_INSTANCES = """
ALTER TABLE workflow_instances ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
"""

CREATE_IDX_WORKFLOW_INSTANCES_ORG = """
CREATE INDEX IF NOT EXISTS idx_workflow_instances_org_id ON workflow_instances(org_id);
"""

# Add org_id to workflow_instance_specialists
ADD_ORG_ID_WORKFLOW_INSTANCE_SPECIALISTS = """
ALTER TABLE workflow_instance_specialists ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
"""

CREATE_IDX_WORKFLOW_INSTANCE_SPECIALISTS_ORG = """
CREATE INDEX IF NOT EXISTS idx_workflow_instance_specialists_org_id ON workflow_instance_specialists(org_id);
"""

# Add org_id to wf_instance_nodes
ADD_ORG_ID_WF_INSTANCE_NODES = """
ALTER TABLE wf_instance_nodes ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
"""

CREATE_IDX_WF_INSTANCE_NODES_ORG = """
CREATE INDEX IF NOT EXISTS idx_wf_instance_nodes_org_id ON wf_instance_nodes(org_id);
"""

# Add org_id to dev_tasks
ADD_ORG_ID_DEV_TASKS = """
ALTER TABLE dev_tasks ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
"""

CREATE_IDX_DEV_TASKS_ORG = """
CREATE INDEX IF NOT EXISTS idx_dev_tasks_org_id ON dev_tasks(org_id);
"""

# Add org_id to task_dependencies
ADD_ORG_ID_TASK_DEPENDENCIES = """
ALTER TABLE task_dependencies ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
"""

CREATE_IDX_TASK_DEPENDENCIES_ORG = """
CREATE INDEX IF NOT EXISTS idx_task_dependencies_org_id ON task_dependencies(org_id);
"""


def migrate_to_multitenancy(db_path: str) -> None:
    """
    Execute Phase 1 migration: Add multitenancy schema.

    Idempotent: safe to call multiple times.

    Args:
        db_path: Path to SQLite database

    Raises:
        sqlite3.DatabaseError: If migration fails
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Create new tables
        print("[MIGRATION] Creating organizations table...")
        cursor.execute(CREATE_ORGANIZATIONS)
        for idx_sql in CREATE_ORGANIZATIONS_INDEXES:
            cursor.execute(idx_sql)

        print("[MIGRATION] Creating users table...")
        cursor.execute(CREATE_USERS)
        for idx_sql in CREATE_USERS_INDEXES:
            cursor.execute(idx_sql)

        print("[MIGRATION] Creating audit_logs table...")
        cursor.execute(CREATE_AUDIT_LOGS)
        for idx_sql in CREATE_AUDIT_LOGS_INDEXES:
            cursor.execute(idx_sql)

        conn.commit()

        # 2. Add org_id to existing tables (independent try/except for each)
        alter_statements = [
            ("workflow_templates", ADD_ORG_ID_WORKFLOW_TEMPLATES, CREATE_IDX_WORKFLOW_TEMPLATES_ORG),
            ("wf_template_phases", ADD_ORG_ID_WF_TEMPLATE_PHASES, CREATE_IDX_WF_TEMPLATE_PHASES_ORG),
            ("wf_template_tasks", ADD_ORG_ID_WF_TEMPLATE_TASKS, CREATE_IDX_WF_TEMPLATE_TASKS_ORG),
            ("agents", ADD_ORG_ID_AGENTS, CREATE_IDX_AGENTS_ORG),
            ("workflow_instances", ADD_ORG_ID_WORKFLOW_INSTANCES, CREATE_IDX_WORKFLOW_INSTANCES_ORG),
            ("workflow_instance_specialists", ADD_ORG_ID_WORKFLOW_INSTANCE_SPECIALISTS, CREATE_IDX_WORKFLOW_INSTANCE_SPECIALISTS_ORG),
            ("wf_instance_nodes", ADD_ORG_ID_WF_INSTANCE_NODES, CREATE_IDX_WF_INSTANCE_NODES_ORG),
            ("dev_tasks", ADD_ORG_ID_DEV_TASKS, CREATE_IDX_DEV_TASKS_ORG),
            ("task_dependencies", ADD_ORG_ID_TASK_DEPENDENCIES, CREATE_IDX_TASK_DEPENDENCIES_ORG),
        ]

        for table_name, alter_sql, index_sql in alter_statements:
            try:
                print(f"[MIGRATION] Adding org_id to {table_name}...")
                cursor.execute(alter_sql)
                cursor.execute(index_sql)
                conn.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"[MIGRATION] {table_name}: Column already exists (idempotent)")
                    conn.rollback()
                elif "no such table" in str(e):
                    print(f"[MIGRATION] {table_name}: Table does not exist (skipping)")
                    conn.rollback()
                else:
                    print(f"[MIGRATION] {table_name}: Error - {e}")
                    conn.rollback()
                    raise

        print("[MIGRATION] Phase 1 migration completed successfully!")

    except Exception as e:
        print(f"[MIGRATION] Fatal error: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


def insert_default_organization(db_path: str) -> None:
    """
    Insert default organization for backward compatibility.

    Args:
        db_path: Path to SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if default org already exists
        cursor.execute("SELECT org_id FROM organizations WHERE org_id = 'default'")
        if cursor.fetchone():
            print("[MIGRATION] Default organization already exists")
            return

        # Insert default organization
        cursor.execute(
            """
            INSERT INTO organizations (org_id, name, slug, tier, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("default", "Default Organization", "default", "free", "active", "system"),
        )
        conn.commit()
        print("[MIGRATION] Default organization inserted")

    except sqlite3.IntegrityError as e:
        print(f"[MIGRATION] Default org already exists: {e}")

    finally:
        conn.close()


if __name__ == "__main__":
    # Example usage
    db_path = str(Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "data" / "tasks.sqlite")
    migrate_to_multitenancy(db_path)
    insert_default_organization(db_path)
