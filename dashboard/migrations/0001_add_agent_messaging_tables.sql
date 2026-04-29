-- Migration: Add Agent Messaging Tables (MVP Phase 1)
-- Date: 2026-04-30
-- Purpose: task_completion_events, webhook_subscriptions, webhook_delivery_logs テーブル作成

-- ============================================================
-- 1. task_completion_events テーブル
-- ============================================================
CREATE TABLE IF NOT EXISTS task_completion_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- イベント基本情報
    task_id INTEGER NOT NULL,
    workflow_id TEXT NOT NULL,
    team_name TEXT NOT NULL,

    -- 実行者情報
    executor_user_id TEXT NOT NULL,
    executor_username TEXT NOT NULL,
    executor_role TEXT NOT NULL CHECK(executor_role IN ('ai-engineer', 'pm', 'em', 'admin')),

    -- タスク完了情報
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    priority INTEGER NOT NULL DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
    completion_time_ms INTEGER,

    -- メタデータ
    tag_ids TEXT,  -- JSON: ["urgent", "mvp"]
    category TEXT CHECK(category IN ('infra', 'feature', 'design', 'test')),
    phase TEXT CHECK(phase IN ('design', 'implementation', 'test', 'review')),

    -- イベント配信状態
    event_status TEXT NOT NULL DEFAULT 'triggered' CHECK(event_status IN ('triggered', 'dispatched', 'acked', 'failed')),

    -- タイムスタンプ
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    triggered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_webhook_attempt_at DATETIME,

    UNIQUE(task_id, triggered_at)
);

CREATE INDEX IF NOT EXISTS idx_task_completion_events_task_id ON task_completion_events(task_id);
CREATE INDEX IF NOT EXISTS idx_task_completion_events_workflow_id ON task_completion_events(workflow_id);
CREATE INDEX IF NOT EXISTS idx_task_completion_events_team_name ON task_completion_events(team_name);
CREATE INDEX IF NOT EXISTS idx_task_completion_events_created_at ON task_completion_events(created_at);
CREATE INDEX IF NOT EXISTS idx_task_completion_events_event_status ON task_completion_events(event_status);

-- ============================================================
-- 2. webhook_subscriptions テーブル
-- ============================================================
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    webhook_id TEXT PRIMARY KEY,

    -- ユーザー情報
    user_id TEXT NOT NULL,

    -- Webhook 基本設定
    name TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'task.completed' CHECK(event_type IN ('task.completed')),
    target_url TEXT NOT NULL,

    -- 認証情報
    auth_type TEXT NOT NULL CHECK(auth_type IN ('bearer', 'hmac-sha256')),
    secret_key_hash TEXT NOT NULL,

    -- 状態
    is_active BOOLEAN NOT NULL DEFAULT 1,

    -- リトライポリシー（JSON）
    retry_policy TEXT NOT NULL DEFAULT '{"max_retries": 3, "retry_backoff_ms": 1000, "timeout_ms": 5000}',

    -- カスタムヘッダ（JSON）
    custom_headers TEXT,

    -- 統計情報
    trigger_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_triggered_at DATETIME,
    last_status_code INTEGER,

    -- 作成・更新情報
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_user_id ON webhook_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_event_type ON webhook_subscriptions(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_is_active ON webhook_subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_created_at ON webhook_subscriptions(created_at);

-- ============================================================
-- 3. webhook_delivery_logs テーブル
-- ============================================================
CREATE TABLE IF NOT EXISTS webhook_delivery_logs (
    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 関連ID
    webhook_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,

    -- 配信情報
    attempt_number INTEGER NOT NULL DEFAULT 1 CHECK(attempt_number >= 1),
    delivery_status TEXT NOT NULL DEFAULT 'pending' CHECK(delivery_status IN ('pending', 'sent', 'acked', 'failed', 'permanent_failure')),

    -- HTTP レスポンス情報
    http_status_code INTEGER,
    response_body TEXT,

    -- リトライ情報
    next_retry_at DATETIME,
    last_error_message TEXT,

    -- タイムスタンプ
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME,

    FOREIGN KEY(webhook_id) REFERENCES webhook_subscriptions(webhook_id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES task_completion_events(event_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_webhook_delivery_logs_webhook_id ON webhook_delivery_logs(webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_delivery_logs_event_id ON webhook_delivery_logs(event_id);
CREATE INDEX IF NOT EXISTS idx_webhook_delivery_logs_delivery_status ON webhook_delivery_logs(delivery_status);
CREATE INDEX IF NOT EXISTS idx_webhook_delivery_logs_next_retry_at ON webhook_delivery_logs(next_retry_at);
CREATE INDEX IF NOT EXISTS idx_webhook_delivery_logs_created_at ON webhook_delivery_logs(created_at);
