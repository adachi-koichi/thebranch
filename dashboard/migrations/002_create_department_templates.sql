-- 部署テンプレート定義（テンプレート層）
-- Phase 1: 人事部・開発部テンプレートスキーマ実装

-- 部署テンプレート定義
CREATE TABLE IF NOT EXISTS departments_templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    category        TEXT NOT NULL,
    version         INTEGER DEFAULT 1,
    status          TEXT DEFAULT 'draft',
    total_roles     INTEGER DEFAULT 0,
    total_processes INTEGER DEFAULT 0,
    total_tasks     INTEGER DEFAULT 0,
    config          TEXT,
    created_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    CHECK(status IN ('draft', 'active', 'deprecated')),
    CHECK(category IN ('back-office', 'tech', 'ops', 'support'))
);

CREATE INDEX IF NOT EXISTS idx_departments_templates_status
  ON departments_templates(status);
CREATE INDEX IF NOT EXISTS idx_departments_templates_category
  ON departments_templates(category);

-- ロール定義
CREATE TABLE IF NOT EXISTS department_template_roles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL REFERENCES departments_templates(id) ON DELETE CASCADE,
    role_key         TEXT NOT NULL,
    role_label       TEXT NOT NULL,
    role_order       INTEGER NOT NULL,
    responsibility   TEXT,
    required_skills  TEXT,
    min_members      INTEGER DEFAULT 1,
    max_members      INTEGER,
    supervisor_role_key TEXT,
    config           TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, role_key),
    UNIQUE(template_id, role_order),
    CHECK(min_members >= 1),
    CHECK(max_members IS NULL OR max_members >= min_members)
);

CREATE INDEX IF NOT EXISTS idx_department_template_roles_template_id
  ON department_template_roles(template_id);

-- プロセス定義
CREATE TABLE IF NOT EXISTS department_template_processes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL REFERENCES departments_templates(id) ON DELETE CASCADE,
    process_key      TEXT NOT NULL,
    process_label    TEXT NOT NULL,
    process_order    INTEGER NOT NULL,
    description      TEXT,
    responsible_role_key TEXT NOT NULL,
    estimated_hours  INTEGER,
    frequency        TEXT,
    doc_requirements TEXT,
    config           TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, process_key),
    UNIQUE(template_id, process_order),
    CHECK(frequency IN ('daily', 'weekly', 'monthly', 'quarterly', 'annual', 'ad-hoc'))
);

CREATE INDEX IF NOT EXISTS idx_department_template_processes_template_id
  ON department_template_processes(template_id);

-- タスク定義
CREATE TABLE IF NOT EXISTS department_template_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id        INTEGER NOT NULL REFERENCES department_template_processes(id) ON DELETE CASCADE,
    template_id       INTEGER NOT NULL REFERENCES departments_templates(id) ON DELETE CASCADE,
    task_key          TEXT NOT NULL,
    task_title        TEXT NOT NULL,
    task_description  TEXT,
    assigned_role_key TEXT NOT NULL,
    category          TEXT,
    estimated_hours   REAL,
    depends_on_key    TEXT,
    priority          INTEGER DEFAULT 3,
    success_criteria  TEXT,
    config            TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(process_id, task_key),
    CHECK(priority IN (1, 2, 3)),
    CHECK(estimated_hours > 0)
);

CREATE INDEX IF NOT EXISTS idx_department_template_tasks_process_id
  ON department_template_tasks(process_id);
