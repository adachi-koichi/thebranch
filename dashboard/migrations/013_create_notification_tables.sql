-- Migration: 013_create_notification_tables.sql
-- Purpose: 通知・アラートシステムの SQLite テーブル作成

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Table: notification_logs
-- 通知ログの統一管理テーブル
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS notification_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 通知の識別
    notification_key    TEXT NOT NULL UNIQUE,  -- "notif-{uuid}"
    notification_type   TEXT NOT NULL CHECK(notification_type IN (
                          'agent_status',
                          'task_delegation',
                          'cost_alert',
                          'approval_request',
                          'error_event',
                          'system_alert'
                        )),

    -- 送信先
    recipient_type      TEXT CHECK(recipient_type IN ('user', 'agent', 'department')),
    recipient_id        TEXT,

    -- 通知内容
    title               TEXT NOT NULL,
    message             TEXT NOT NULL,
    severity            TEXT DEFAULT 'info' CHECK(severity IN ('info', 'warning', 'error', 'critical')),

    -- 参照情報
    source_table        TEXT,  -- 'agents', 'task_delegations', 'cost_alerts', 'agent_logs' など
    source_id           INTEGER,

    -- メタデータ
    metadata            TEXT,  -- JSON形式
    action_url          TEXT,  -- UI への遷移先

    -- ステータス管理
    status              TEXT DEFAULT 'unread' CHECK(status IN ('unread', 'read', 'acknowledged', 'archived')),
    read_at             TEXT,
    acknowledged_at     TEXT,

    -- タイムスタンプ
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- インデックス（クエリ最適化）
CREATE INDEX IF NOT EXISTS idx_notification_logs_recipient
  ON notification_logs(recipient_type, recipient_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_logs_type
  ON notification_logs(notification_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_logs_status
  ON notification_logs(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_logs_severity
  ON notification_logs(severity, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_logs_created_at
  ON notification_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_logs_source
  ON notification_logs(source_table, source_id);

CREATE INDEX IF NOT EXISTS idx_notification_logs_unread
  ON notification_logs(recipient_id, status) WHERE status = 'unread';


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Table: notification_preferences
-- ユーザー・エージェント別の通知設定
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS notification_preferences (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 対象者
    recipient_id        TEXT NOT NULL,  -- user_id, agent_id
    recipient_type      TEXT NOT NULL CHECK(recipient_type IN ('user', 'agent', 'department')),

    -- 通知タイプ別設定
    agent_status_enabled BOOLEAN DEFAULT 1,
    task_delegation_enabled BOOLEAN DEFAULT 1,
    cost_alert_enabled  BOOLEAN DEFAULT 1,
    approval_request_enabled BOOLEAN DEFAULT 1,
    error_event_enabled BOOLEAN DEFAULT 1,
    system_alert_enabled BOOLEAN DEFAULT 1,

    -- 重要度フィルター（この重大度以上を表示）
    min_severity        TEXT DEFAULT 'info' CHECK(min_severity IN ('info', 'warning', 'error', 'critical')),

    -- チャネル設定
    notify_via_dashboard BOOLEAN DEFAULT 1,
    notify_via_email    BOOLEAN DEFAULT 0,
    notify_via_slack    BOOLEAN DEFAULT 0,

    -- タイムスタンプ
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    UNIQUE(recipient_id, recipient_type)
);

CREATE INDEX IF NOT EXISTS idx_notification_preferences_recipient
  ON notification_preferences(recipient_id, recipient_type);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Table: notification_summary
-- 日単位の通知集計テーブル
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS notification_summary (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 対象者
    recipient_id        TEXT NOT NULL,
    recipient_type      TEXT NOT NULL,

    -- 日付
    summary_date        TEXT NOT NULL,  -- YYYY-MM-DD

    -- 通知タイプ別集計
    agent_status_count  INTEGER DEFAULT 0,
    task_delegation_count INTEGER DEFAULT 0,
    cost_alert_count    INTEGER DEFAULT 0,
    approval_request_count INTEGER DEFAULT 0,
    error_event_count   INTEGER DEFAULT 0,
    system_alert_count  INTEGER DEFAULT 0,

    -- 重要度別集計
    critical_count      INTEGER DEFAULT 0,
    error_count         INTEGER DEFAULT 0,
    warning_count       INTEGER DEFAULT 0,
    info_count          INTEGER DEFAULT 0,

    -- ステータス
    unread_count        INTEGER DEFAULT 0,
    read_count          INTEGER DEFAULT 0,

    -- タイムスタンプ
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    UNIQUE(recipient_id, recipient_type, summary_date)
);

CREATE INDEX IF NOT EXISTS idx_notification_summary_date
  ON notification_summary(recipient_id, summary_date DESC);
