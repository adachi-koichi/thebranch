-- 部署インスタンス定義（インスタンス層）
-- Phase 1: 人事部・開発部インスタンス化スキーマ実装

-- 部署インスタンス
CREATE TABLE IF NOT EXISTS department_instances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id     INTEGER NOT NULL REFERENCES departments_templates(id),
    name            TEXT NOT NULL,
    status          TEXT DEFAULT 'active',
    organization_id TEXT,
    location        TEXT,
    manager_agent_id INTEGER REFERENCES agents(id),
    context         TEXT,
    member_count    INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    started_at      TEXT,
    closed_at       TEXT,
    CHECK(status IN ('planning', 'active', 'suspended', 'closed'))
);

CREATE INDEX IF NOT EXISTS idx_department_instances_template_id
  ON department_instances(template_id);
CREATE INDEX IF NOT EXISTS idx_department_instances_status
  ON department_instances(status);

-- メンバー割り当て
CREATE TABLE IF NOT EXISTS department_instance_members (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id      INTEGER NOT NULL REFERENCES department_instances(id) ON DELETE CASCADE,
    agent_id         INTEGER NOT NULL REFERENCES agents(id),
    role_key         TEXT NOT NULL,
    status           TEXT DEFAULT 'active',
    start_date       TEXT NOT NULL DEFAULT (date('now')),
    end_date         TEXT,
    assigned_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, agent_id),
    CHECK(status IN ('active', 'inactive', 'on-leave'))
);

CREATE INDEX IF NOT EXISTS idx_department_instance_members_instance_id
  ON department_instance_members(instance_id);
CREATE INDEX IF NOT EXISTS idx_department_instance_members_agent_id
  ON department_instance_members(agent_id);

-- プロセス実行ワークフロー
CREATE TABLE IF NOT EXISTS department_instance_workflows (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id           INTEGER NOT NULL REFERENCES department_instances(id) ON DELETE CASCADE,
    process_id            INTEGER NOT NULL REFERENCES department_template_processes(id),
    workflow_instance_id  INTEGER REFERENCES workflow_instances(id),
    execution_count       INTEGER DEFAULT 1,
    status                TEXT DEFAULT 'pending',
    scheduled_date        TEXT,
    started_at            TEXT,
    completed_at          TEXT,
    result_notes          TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, process_id, execution_count),
    CHECK(status IN ('pending', 'running', 'completed', 'failed', 'paused'))
);

CREATE INDEX IF NOT EXISTS idx_department_instance_workflows_instance_id
  ON department_instance_workflows(instance_id);
CREATE INDEX IF NOT EXISTS idx_department_instance_workflows_status
  ON department_instance_workflows(status);
