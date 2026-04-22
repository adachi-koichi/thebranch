-- Task Delegation Schema Migration
-- Created: 2026-04-20
-- Purpose: Support agent-to-agent task delegation with chain tracking

-- Table 1: task_delegations (委譲トランザクション管理)
CREATE TABLE IF NOT EXISTS task_delegations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 委譲の基本情報
    delegation_key        TEXT NOT NULL UNIQUE,  -- "deleg-{timestamp}-{uuid}"
    task_id               INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,

    -- 委譲関係
    from_agent_id         TEXT NOT NULL,  -- 委譲元エージェント ID
    to_agent_id           TEXT NOT NULL,  -- 委譲先エージェント ID
    from_agent_type       TEXT NOT NULL CHECK(from_agent_type IN ('orchestrator', 'em', 'engineer')),
    to_agent_type         TEXT NOT NULL CHECK(to_agent_type IN ('em', 'engineer')),

    -- 委譲コンテキスト
    delegation_scope      TEXT NOT NULL CHECK(delegation_scope IN ('workflow', 'phase', 'task')),
    scope_reference_id    INTEGER,  -- workflow_id / phase_id の参照
    scope_reference_key   TEXT,     -- 'workflow-001' / 'phase-02' など

    -- 委譲メッセージ
    delegation_message    TEXT,     -- 委譲時のメッセージ（期待される完了期限など）

    -- ステータス管理
    status                TEXT NOT NULL DEFAULT 'pending'
                          CHECK(status IN (
                            'pending',           -- 委譲待機（受信側未確認）
                            'acknowledged',      -- 受信側が確認応答
                            'in_progress',       -- 実行中
                            'completed',         -- 完了
                            'rejected',          -- 委譲拒否
                            'reassigned'         -- 再委譲（他のエージェントへ）
                          )),

    -- タイムスタンプ
    delegated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    acknowledged_at       TEXT,  -- 受信側が確認した時刻
    started_at            TEXT,  -- 実作業開始時刻
    completed_at          TEXT,

    -- トレーサビリティ
    parent_delegation_id  INTEGER REFERENCES task_delegations(id),  -- 再委譲元
    retry_attempt         INTEGER DEFAULT 0,  -- リトライ回数

    -- メタデータ
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_delegation_id) REFERENCES task_delegations(id) ON DELETE SET NULL
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_task_delegations_task_id ON task_delegations(task_id);
CREATE INDEX IF NOT EXISTS idx_task_delegations_from_agent ON task_delegations(from_agent_id);
CREATE INDEX IF NOT EXISTS idx_task_delegations_to_agent ON task_delegations(to_agent_id);
CREATE INDEX IF NOT EXISTS idx_task_delegations_status ON task_delegations(status);
CREATE INDEX IF NOT EXISTS idx_task_delegations_delegation_key ON task_delegations(delegation_key);
CREATE INDEX IF NOT EXISTS idx_task_delegations_scope_reference ON task_delegations(scope_reference_id);

---

-- Table 2: delegation_events (委譲イベントログ)
CREATE TABLE IF NOT EXISTS delegation_events (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,

    -- イベントの関連付け
    delegation_id         INTEGER NOT NULL REFERENCES task_delegations(id) ON DELETE CASCADE,
    task_id               INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,

    -- イベント情報
    event_type            TEXT NOT NULL CHECK(event_type IN (
                            'delegated',        -- タスク委譲実行
                            'acknowledged',     -- 受信側が確認応答
                            'rejected',         -- 委譲拒否
                            'started',          -- 実作業開始
                            'completed',        -- 完了
                            'error',            -- エラー発生
                            'reassigned',       -- 再委譲
                            'commented'         -- コメント追加
                          )),

    -- アクター情報
    actor_id              TEXT NOT NULL,
    actor_type            TEXT NOT NULL CHECK(actor_type IN ('orchestrator', 'em', 'engineer')),
    actor_name            TEXT,

    -- イベント詳細
    message               TEXT,
    metadata              TEXT,  -- JSON: 詳細情報（エラー詳細など）

    -- タイムスタンプ
    event_timestamp       TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    FOREIGN KEY (delegation_id) REFERENCES task_delegations(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_delegation_events_delegation_id ON delegation_events(delegation_id);
CREATE INDEX IF NOT EXISTS idx_delegation_events_task_id ON delegation_events(task_id);
CREATE INDEX IF NOT EXISTS idx_delegation_events_event_type ON delegation_events(event_type);
CREATE INDEX IF NOT EXISTS idx_delegation_events_actor_id ON delegation_events(actor_id);
CREATE INDEX IF NOT EXISTS idx_delegation_events_timestamp ON delegation_events(event_timestamp);

---

-- Table 3: delegation_comments (委譲に関するコメント・メモ)
CREATE TABLE IF NOT EXISTS delegation_comments (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,

    -- コメント対象
    delegation_id         INTEGER NOT NULL REFERENCES task_delegations(id) ON DELETE CASCADE,
    task_id               INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,

    -- コメント情報
    author_id             TEXT NOT NULL,
    author_type           TEXT NOT NULL CHECK(author_type IN ('orchestrator', 'em', 'engineer')),
    content               TEXT NOT NULL,

    -- メタデータ
    comment_type          TEXT DEFAULT 'note'  -- 'note', 'risk', 'blocker', 'update'
                          CHECK(comment_type IN ('note', 'risk', 'blocker', 'update')),

    -- タイムスタンプ
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    FOREIGN KEY (delegation_id) REFERENCES task_delegations(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_delegation_comments_delegation_id ON delegation_comments(delegation_id);
CREATE INDEX IF NOT EXISTS idx_delegation_comments_task_id ON delegation_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_delegation_comments_author_id ON delegation_comments(author_id);

---

-- Note: ALTER TABLE IF NOT EXISTS not supported in SQLite < 3.35.0
-- These columns can be added manually if needed
