-- Migration: 036_create_agent_chats.sql
-- Purpose: エージェントチャット履歴の永続化 (Task #2509)
--   - agent_chats: 部署内AIエージェントとのチャット会話ログ
--     - role: 'user' | 'assistant' | 'system' のいずれか
--     - session_id: ブラウザ側で発行する会話セッション識別子
--     - context_meta: 任意の付帯情報（履歴件数・モデル名など、JSON 文字列）
-- Created: 2026-04-26

CREATE TABLE IF NOT EXISTS agent_chats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        INTEGER NOT NULL,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL
        CHECK(role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    context_meta    TEXT,
    user_id         TEXT,
    username        TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_chats_agent_id    ON agent_chats(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_chats_session     ON agent_chats(agent_id, session_id);
CREATE INDEX IF NOT EXISTS idx_agent_chats_created_at  ON agent_chats(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_chats_role        ON agent_chats(role);
