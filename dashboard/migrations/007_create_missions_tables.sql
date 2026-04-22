-- Mission テーブル（エージェント↔ワークフロー の紐付け）
CREATE TABLE IF NOT EXISTS missions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id              INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    department_id         INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    workflow_id           INTEGER NOT NULL REFERENCES department_instance_workflows(id) ON DELETE CASCADE,
    name                  TEXT NOT NULL,
    description           TEXT,
    status                TEXT DEFAULT 'planning'
                          CHECK(status IN ('planning', 'active', 'paused', 'completed', 'cancelled')),
    priority              INTEGER DEFAULT 3,
    custom_prompt         TEXT,
    target_completion     TEXT,
    actual_completion     TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(agent_id, workflow_id)
);

-- Mission に割り当てるタスク群
CREATE TABLE IF NOT EXISTS mission_tasks (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id            INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    task_key              TEXT NOT NULL,
    task_title            TEXT NOT NULL,
    status                TEXT DEFAULT 'pending'
                          CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    assigned_role_key     TEXT,
    priority              INTEGER DEFAULT 3,
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(mission_id, task_key)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_missions_agent_id ON missions(agent_id);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_missions_department_id ON missions(department_id);
CREATE INDEX IF NOT EXISTS idx_mission_tasks_mission_id ON mission_tasks(mission_id);
