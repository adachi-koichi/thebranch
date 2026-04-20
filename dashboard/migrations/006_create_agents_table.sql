-- AIエージェント管理テーブル
-- tmux セッション管理・エージェントライフサイクル追跡用

CREATE TABLE IF NOT EXISTS agents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    session_id    TEXT NOT NULL UNIQUE,
    role          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'starting',
    started_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    stopped_at    TEXT,
    error_message TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    CHECK(status IN ('starting', 'running', 'stopped', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_agents_department_id ON agents(department_id);
CREATE INDEX IF NOT EXISTS idx_agents_session_id ON agents(session_id);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_created_at ON agents(created_at);
