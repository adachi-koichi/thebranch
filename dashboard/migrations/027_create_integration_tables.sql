-- Migration: 027_create_integration_tables.sql
-- Purpose: Slack/Discord 統合設定とWebhookイベントのテーブル作成

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Table: integration_configs - 統合設定
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS integration_configs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_type    TEXT NOT NULL CHECK(integration_type IN ('slack','discord')),
    organization_id     TEXT NOT NULL,
    webhook_url         TEXT NOT NULL,
    webhook_secret      TEXT NOT NULL,
    channel_id          TEXT,
    channel_name        TEXT,
    is_active           INTEGER DEFAULT 1,
    notify_on_agent_status     INTEGER DEFAULT 1,
    notify_on_task_delegation  INTEGER DEFAULT 1,
    notify_on_cost_alert       INTEGER DEFAULT 1,
    notify_on_approval_request INTEGER DEFAULT 1,
    notify_on_error_event      INTEGER DEFAULT 1,
    notify_on_system_alert     INTEGER DEFAULT 1,
    metadata            TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    last_verified_at    TEXT,
    UNIQUE(integration_type, webhook_url)
);

CREATE INDEX IF NOT EXISTS idx_integration_configs_org
  ON integration_configs(organization_id, integration_type, is_active);

CREATE INDEX IF NOT EXISTS idx_integration_configs_active
  ON integration_configs(is_active, integration_type);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Table: webhook_events - Webhook 受信ログ
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS webhook_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id            TEXT NOT NULL UNIQUE,
    integration_config_id INTEGER,
    event_type          TEXT NOT NULL,
    event_source        TEXT NOT NULL CHECK(event_source IN ('slack','discord')),
    raw_payload         TEXT NOT NULL,
    parsed_data         TEXT,
    processing_status   TEXT DEFAULT 'received'
                        CHECK(processing_status IN ('received','validated','processed','failed','ignored')),
    error_message       TEXT,
    notification_id     INTEGER,
    received_at         TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    processed_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_config
  ON webhook_events(integration_config_id, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_webhook_events_status
  ON webhook_events(processing_status, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_webhook_events_event_id
  ON webhook_events(event_id);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Table: notification_logs 拡張
-- Slack/Discord統合用カラムを追加
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALTER TABLE notification_logs ADD COLUMN slack_message_id TEXT;
ALTER TABLE notification_logs ADD COLUMN discord_message_id TEXT;
ALTER TABLE notification_logs ADD COLUMN integration_config_id INTEGER;
