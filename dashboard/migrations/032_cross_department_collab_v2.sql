-- Migration: 032_cross_department_collab_v2.sql
-- Purpose: 部署間コラボレーション機能テーブル追加 (Task #2486)
--   - cross_department_tasks: クロス部署タスク依頼
--   - dept_collab_notifications: 部署間通知
-- Note: departments テーブル（not department_instances）を参照
-- Created: 2026-04-26

-- 1. クロス部署タスク依頼テーブル
CREATE TABLE IF NOT EXISTS cross_department_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    requesting_dept_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    receiving_dept_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    linked_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'acknowledged', 'in_progress', 'completed', 'rejected')),
    deadline TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_cdt_requesting ON cross_department_tasks(requesting_dept_id);
CREATE INDEX IF NOT EXISTS idx_cdt_receiving ON cross_department_tasks(receiving_dept_id);
CREATE INDEX IF NOT EXISTS idx_cdt_status ON cross_department_tasks(status);
CREATE INDEX IF NOT EXISTS idx_cdt_created ON cross_department_tasks(created_at DESC);

-- 2. 部署間コラボレーション通知テーブル
CREATE TABLE IF NOT EXISTS dept_collab_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cross_task_id INTEGER NOT NULL REFERENCES cross_department_tasks(id) ON DELETE CASCADE,
    sender_dept_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    receiver_dept_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL CHECK(notification_type IN (
        'new_request', 'status_update', 'completed', 'rejected', 'comment'
    )),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    read_at TEXT,
    metadata TEXT,  -- JSON
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_dcn_receiver ON dept_collab_notifications(receiver_dept_id, is_read);
CREATE INDEX IF NOT EXISTS idx_dcn_cross_task ON dept_collab_notifications(cross_task_id);
CREATE INDEX IF NOT EXISTS idx_dcn_created ON dept_collab_notifications(created_at DESC);
