-- 011_create_projects_tables.sql
-- プロジェクト管理テーブル
-- Project > Workflow > Task の3階層構造

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    DEFAULT '',
    status      TEXT    DEFAULT 'active' CHECK(status IN ('active', 'archived', 'draft')),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- プロジェクトとワークフローテンプレートの関連
CREATE TABLE IF NOT EXISTS project_workflows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workflow_id     INTEGER NOT NULL REFERENCES workflow_templates(id) ON DELETE CASCADE,
    workflow_order  INTEGER DEFAULT 0,
    -- sequential: 前のワークフロー完了後に実行
    -- parallel: 前のワークフローと並行実行
    execution_mode  TEXT    DEFAULT 'sequential' CHECK(execution_mode IN ('sequential', 'parallel')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, workflow_id)
);

CREATE INDEX IF NOT EXISTS idx_project_workflows_project ON project_workflows(project_id);
CREATE INDEX IF NOT EXISTS idx_project_workflows_workflow ON project_workflows(workflow_id);
