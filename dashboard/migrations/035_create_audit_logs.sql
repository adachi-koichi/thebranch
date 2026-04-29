-- Migration: 035_create_audit_logs.sql
-- Purpose: 監査ログ機能 (Task #2501)
--   - audit_logs: ユーザー操作監査ログ（ログイン、CRUD、設定変更などの操作履歴）
-- Created: 2026-04-26

CREATE TABLE IF NOT EXISTS audit_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT,
    username        TEXT,
    action          TEXT NOT NULL,
    -- action: 'login', 'logout', 'create', 'update', 'delete', 'access', 'config_change', 'permission_change'
    resource_type   TEXT,
    -- resource_type: 'agent', 'department', 'team', 'task', 'user', 'role', 'collab_request' など
    resource_id     TEXT,
    detail          TEXT,
    ip_address      TEXT,
    user_agent      TEXT,
    status          TEXT NOT NULL DEFAULT 'success'
        CHECK(status IN ('success', 'failure', 'denied')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id     ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action      ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource    ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at  ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_status      ON audit_logs(status);
