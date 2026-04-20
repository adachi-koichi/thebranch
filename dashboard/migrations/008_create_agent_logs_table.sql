-- エージェント活動ログテーブル
-- エージェントの起動・停止・エラーなどアクティビティを時系列に記録

CREATE TABLE IF NOT EXISTS agent_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id      INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    action        TEXT NOT NULL,
    detail        TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    CHECK(action IN ('started', 'stopped', 'failed', 'message'))
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_agent_id ON agent_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_created_at ON agent_logs(created_at);
