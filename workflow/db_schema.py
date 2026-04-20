"""
Database schema definitions for workflow system.

Handles SQLite table creation with idempotency (IF NOT EXISTS).
Organized by layer: template, instance, task, specialist.
Follows data-model.md (Phase 4) specifications.
"""

# ===== TEMPLATE LAYER =====

CREATE_WORKFLOW_TEMPLATES = """
CREATE TABLE IF NOT EXISTS workflow_templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    category        TEXT,
    version         INTEGER DEFAULT 1,
    status          TEXT DEFAULT 'draft'
                    CHECK(status IN ('draft', 'active', 'deprecated')),
    owner_id        INTEGER,
    organization_id INTEGER,
    phase_count     INTEGER DEFAULT 0,
    task_count      INTEGER DEFAULT 0,
    estimated_hours INTEGER,
    tags            TEXT,
    config          TEXT,
    created_by      TEXT,
    updated_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

CREATE_IDX_WORKFLOW_TEMPLATES_STATUS = """
CREATE INDEX IF NOT EXISTS idx_workflow_templates_status
    ON workflow_templates(status);
"""

CREATE_IDX_WORKFLOW_TEMPLATES_CREATED_AT = """
CREATE INDEX IF NOT EXISTS idx_workflow_templates_created_at
    ON workflow_templates(created_at);
"""

CREATE_IDX_WORKFLOW_TEMPLATES_ORGANIZATION = """
CREATE INDEX IF NOT EXISTS idx_workflow_templates_organization_id
    ON workflow_templates(organization_id);
"""

CREATE_IDX_WORKFLOW_TEMPLATES_CATEGORY = """
CREATE INDEX IF NOT EXISTS idx_workflow_templates_category
    ON workflow_templates(category);
"""

CREATE_WF_TEMPLATE_PHASES = """
CREATE TABLE IF NOT EXISTS wf_template_phases (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL REFERENCES workflow_templates(id) ON DELETE CASCADE,
    phase_key        TEXT NOT NULL,
    phase_order      INTEGER NOT NULL,
    phase_label      TEXT NOT NULL,
    description      TEXT,
    specialist_type  TEXT NOT NULL,
    specialist_count INTEGER DEFAULT 1,
    is_parallel      BOOLEAN DEFAULT 0,
    task_count       INTEGER DEFAULT 0,
    estimated_hours  INTEGER,
    config           TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, phase_key),
    UNIQUE(template_id, phase_order),
    FOREIGN KEY(template_id) REFERENCES workflow_templates(id) ON DELETE CASCADE
);
"""

CREATE_IDX_WF_TEMPLATE_PHASES_TEMPLATE_ID = """
CREATE INDEX IF NOT EXISTS idx_wf_template_phases_template_id
    ON wf_template_phases(template_id);
"""

CREATE_IDX_WF_TEMPLATE_PHASES_PHASE_ORDER = """
CREATE INDEX IF NOT EXISTS idx_wf_template_phases_phase_order
    ON wf_template_phases(template_id, phase_order);
"""

CREATE_WF_TEMPLATE_TASKS = """
CREATE TABLE IF NOT EXISTS wf_template_tasks (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id          INTEGER NOT NULL REFERENCES workflow_templates(id) ON DELETE CASCADE,
    phase_id             INTEGER NOT NULL REFERENCES wf_template_phases(id) ON DELETE CASCADE,
    task_key             TEXT NOT NULL,
    task_title           TEXT NOT NULL,
    task_description     TEXT,
    category             TEXT,
    priority             INTEGER DEFAULT 3,
    estimated_hours      INTEGER,
    depends_on_key       TEXT,
    acceptance_criteria  TEXT,
    tags                 TEXT,
    config               TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(phase_id, task_key),
    FOREIGN KEY(template_id) REFERENCES workflow_templates(id) ON DELETE CASCADE,
    FOREIGN KEY(phase_id) REFERENCES wf_template_phases(id) ON DELETE CASCADE
);
"""

CREATE_IDX_WF_TEMPLATE_TASKS_PHASE_ID = """
CREATE INDEX IF NOT EXISTS idx_wf_template_tasks_phase_id
    ON wf_template_tasks(phase_id);
"""

CREATE_IDX_WF_TEMPLATE_TASKS_TEMPLATE_ID = """
CREATE INDEX IF NOT EXISTS idx_wf_template_tasks_template_id
    ON wf_template_tasks(template_id);
"""

# ===== SPECIALIST LAYER =====

CREATE_AGENTS = """
CREATE TABLE IF NOT EXISTS agents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT UNIQUE,
    slug            TEXT UNIQUE,
    specialist_type TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

CREATE_IDX_AGENTS_SLUG = """
CREATE INDEX IF NOT EXISTS idx_agents_slug
    ON agents(slug);
"""

CREATE_IDX_AGENTS_EMAIL = """
CREATE INDEX IF NOT EXISTS idx_agents_email
    ON agents(email);
"""

# ===== INSTANCE LAYER =====

CREATE_WORKFLOW_INSTANCES = """
CREATE TABLE IF NOT EXISTS workflow_instances (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id       INTEGER NOT NULL REFERENCES workflow_templates(id),
    name              TEXT NOT NULL,
    status            TEXT DEFAULT 'pending'
                      CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    current_phase_key TEXT,
    context           TEXT,
    created_by        TEXT,
    project_id        INTEGER,
    project           TEXT,
    organization_id   INTEGER,
    estimated_hours   INTEGER,
    actual_hours      REAL,
    start_time        TEXT,
    end_time          TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    started_at        TEXT,
    completed_at      TEXT
);
"""

CREATE_IDX_WORKFLOW_INSTANCES_TEMPLATE_ID = """
CREATE INDEX IF NOT EXISTS idx_workflow_instances_template_id
    ON workflow_instances(template_id);
"""

CREATE_IDX_WORKFLOW_INSTANCES_STATUS = """
CREATE INDEX IF NOT EXISTS idx_workflow_instances_status
    ON workflow_instances(status);
"""

CREATE_IDX_WORKFLOW_INSTANCES_CREATED_AT = """
CREATE INDEX IF NOT EXISTS idx_workflow_instances_created_at
    ON workflow_instances(created_at);
"""

CREATE_WORKFLOW_INSTANCE_SPECIALISTS = """
CREATE TABLE IF NOT EXISTS workflow_instance_specialists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id       INTEGER NOT NULL REFERENCES workflow_instances(id),
    phase_id          INTEGER NOT NULL REFERENCES wf_template_phases(id),
    phase_key         TEXT NOT NULL,
    specialist_id     INTEGER NOT NULL REFERENCES agents(id),
    specialist_slug   TEXT NOT NULL,
    specialist_name   TEXT NOT NULL,
    specialist_role   TEXT NOT NULL,
    assigned_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, phase_id)
);
"""

CREATE_IDX_WORKFLOW_INSTANCE_SPECIALISTS_INSTANCE_ID = """
CREATE INDEX IF NOT EXISTS idx_workflow_instance_specialists_instance_id
    ON workflow_instance_specialists(instance_id);
"""

CREATE_IDX_WORKFLOW_INSTANCE_SPECIALISTS_SPECIALIST_ID = """
CREATE INDEX IF NOT EXISTS idx_workflow_instance_specialists_specialist_id
    ON workflow_instance_specialists(specialist_id);
"""

# ===== PHASE INSTANCE NODES =====

CREATE_WF_INSTANCE_NODES = """
CREATE TABLE IF NOT EXISTS wf_instance_nodes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id         INTEGER NOT NULL REFERENCES workflow_instances(id) ON DELETE CASCADE,
    phase_id            INTEGER NOT NULL REFERENCES wf_template_phases(id),
    phase_key           TEXT NOT NULL,
    node_key            TEXT,
    node_type           TEXT DEFAULT 'task',
    status              TEXT DEFAULT 'waiting'
                        CHECK(status IN ('waiting', 'ready', 'running', 'completed', 'failed', 'skipped')),
    task_id             INTEGER REFERENCES dev_tasks(id),
    task_ids            TEXT,
    result              TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    started_at          TEXT,
    completed_at        TEXT,
    UNIQUE(instance_id, phase_id),
    FOREIGN KEY(instance_id) REFERENCES workflow_instances(id) ON DELETE CASCADE,
    FOREIGN KEY(phase_id) REFERENCES wf_template_phases(id)
);
"""

CREATE_IDX_WF_INSTANCE_NODES_INSTANCE_ID = """
CREATE INDEX IF NOT EXISTS idx_wf_instance_nodes_instance_id
    ON wf_instance_nodes(instance_id);
"""

CREATE_IDX_WF_INSTANCE_NODES_PHASE_ID = """
CREATE INDEX IF NOT EXISTS idx_wf_instance_nodes_phase_id
    ON wf_instance_nodes(phase_id);
"""

CREATE_IDX_WF_INSTANCE_NODES_STATUS = """
CREATE INDEX IF NOT EXISTS idx_wf_instance_nodes_status
    ON wf_instance_nodes(status);
"""

CREATE_IDX_WF_INSTANCE_NODES_TASK_ID = """
CREATE INDEX IF NOT EXISTS idx_wf_instance_nodes_task_id
    ON wf_instance_nodes(task_id);
"""

# ===== TASK LAYER =====

CREATE_DEV_TASKS = """
CREATE TABLE IF NOT EXISTS dev_tasks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT NOT NULL,
    description         TEXT,
    status              TEXT DEFAULT 'blocked',
    priority            INTEGER DEFAULT 1,
    category            TEXT,
    assignee            TEXT,
    practitioner_id     INTEGER REFERENCES agents(id),
    practitioner_status TEXT,
    phase               TEXT,
    workflow_instance_id INTEGER REFERENCES workflow_instances(id),
    wf_node_key         TEXT,
    estimated_hours     REAL,
    version             INTEGER DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    started_at          TEXT,
    completed_at        TEXT,
    unblocked_at        TEXT
);
"""

CREATE_IDX_DEV_TASKS_STATUS = """
CREATE INDEX IF NOT EXISTS idx_dev_tasks_status
    ON dev_tasks(status);
"""

CREATE_IDX_DEV_TASKS_ASSIGNEE = """
CREATE INDEX IF NOT EXISTS idx_dev_tasks_assignee
    ON dev_tasks(assignee);
"""

CREATE_IDX_DEV_TASKS_WORKFLOW_INSTANCE_ID = """
CREATE INDEX IF NOT EXISTS idx_dev_tasks_workflow_instance_id
    ON dev_tasks(workflow_instance_id);
"""

CREATE_IDX_DEV_TASKS_PHASE = """
CREATE INDEX IF NOT EXISTS idx_dev_tasks_phase
    ON dev_tasks(phase);
"""

CREATE_TASK_DEPENDENCIES = """
CREATE TABLE IF NOT EXISTS task_dependencies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    predecessor_id  INTEGER NOT NULL REFERENCES dev_tasks(id),
    successor_id    INTEGER NOT NULL REFERENCES dev_tasks(id),
    dep_type        TEXT DEFAULT 'inter_phase',
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(predecessor_id, successor_id)
);
"""

CREATE_IDX_TASK_DEPENDENCIES_PREDECESSOR_ID = """
CREATE INDEX IF NOT EXISTS idx_task_dependencies_predecessor_id
    ON task_dependencies(predecessor_id);
"""

CREATE_IDX_TASK_DEPENDENCIES_SUCCESSOR_ID = """
CREATE INDEX IF NOT EXISTS idx_task_dependencies_successor_id
    ON task_dependencies(successor_id);
"""

# ===== SCHEMA INITIALIZATION =====

ALL_CREATE_STATEMENTS = [
    # Template layer
    CREATE_WORKFLOW_TEMPLATES,
    CREATE_IDX_WORKFLOW_TEMPLATES_STATUS,
    CREATE_IDX_WORKFLOW_TEMPLATES_CREATED_AT,
    CREATE_IDX_WORKFLOW_TEMPLATES_ORGANIZATION,
    CREATE_IDX_WORKFLOW_TEMPLATES_CATEGORY,
    CREATE_WF_TEMPLATE_PHASES,
    CREATE_IDX_WF_TEMPLATE_PHASES_TEMPLATE_ID,
    CREATE_IDX_WF_TEMPLATE_PHASES_PHASE_ORDER,
    CREATE_WF_TEMPLATE_TASKS,
    CREATE_IDX_WF_TEMPLATE_TASKS_PHASE_ID,
    CREATE_IDX_WF_TEMPLATE_TASKS_TEMPLATE_ID,

    # Specialist layer
    CREATE_AGENTS,
    CREATE_IDX_AGENTS_SLUG,
    CREATE_IDX_AGENTS_EMAIL,

    # Instance layer
    CREATE_WORKFLOW_INSTANCES,
    CREATE_IDX_WORKFLOW_INSTANCES_TEMPLATE_ID,
    CREATE_IDX_WORKFLOW_INSTANCES_STATUS,
    CREATE_IDX_WORKFLOW_INSTANCES_CREATED_AT,
    CREATE_WORKFLOW_INSTANCE_SPECIALISTS,
    CREATE_IDX_WORKFLOW_INSTANCE_SPECIALISTS_INSTANCE_ID,
    CREATE_IDX_WORKFLOW_INSTANCE_SPECIALISTS_SPECIALIST_ID,

    # Phase instance layer
    CREATE_WF_INSTANCE_NODES,
    CREATE_IDX_WF_INSTANCE_NODES_INSTANCE_ID,
    CREATE_IDX_WF_INSTANCE_NODES_PHASE_ID,
    CREATE_IDX_WF_INSTANCE_NODES_STATUS,
    CREATE_IDX_WF_INSTANCE_NODES_TASK_ID,

    # Task layer
    CREATE_DEV_TASKS,
    CREATE_IDX_DEV_TASKS_STATUS,
    CREATE_IDX_DEV_TASKS_ASSIGNEE,
    CREATE_IDX_DEV_TASKS_WORKFLOW_INSTANCE_ID,
    CREATE_IDX_DEV_TASKS_PHASE,
    CREATE_TASK_DEPENDENCIES,
    CREATE_IDX_TASK_DEPENDENCIES_PREDECESSOR_ID,
    CREATE_IDX_TASK_DEPENDENCIES_SUCCESSOR_ID,
]


def initialize_schema(connection) -> None:
    """
    Initialize database schema.

    Idempotent: runs all CREATE TABLE IF NOT EXISTS statements.
    Safe to call multiple times.

    Args:
        connection: sqlite3 connection object

    Raises:
        sqlite3.DatabaseError: If schema creation fails
    """
    cursor = connection.cursor()

    # Enable foreign key constraints
    cursor.execute('PRAGMA foreign_keys = ON;')

    for statement in ALL_CREATE_STATEMENTS:
        if statement.strip():
            cursor.execute(statement.strip())

    connection.commit()


# Legacy support: single SQL string for tests using executescript()
WORKFLOW_SCHEMA = '\n'.join([s.strip() for s in ALL_CREATE_STATEMENTS if s.strip()])
