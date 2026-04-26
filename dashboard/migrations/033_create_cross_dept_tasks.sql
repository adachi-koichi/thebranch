-- Migration: 033_create_cross_dept_tasks.sql
-- Purpose: 部署間コラボレーション機能 (Task #2486)
--   - cross_dept_tasks: 部署間タスク依頼テーブル
-- Note: from_dept_id / to_dept_id は departments(id) を参照
--       （teams.department_id → departments(id) との整合性のため）
-- Created: 2026-04-26

-- 部署間タスク依頼テーブル
CREATE TABLE IF NOT EXISTS cross_dept_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_dept_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    to_dept_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    task_name TEXT NOT NULL,
    task_description TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'accepted', 'rejected')),
    created_by TEXT,
    reject_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_cross_dept_tasks_from_dept
    ON cross_dept_tasks(from_dept_id);
CREATE INDEX IF NOT EXISTS idx_cross_dept_tasks_to_dept
    ON cross_dept_tasks(to_dept_id);
CREATE INDEX IF NOT EXISTS idx_cross_dept_tasks_status
    ON cross_dept_tasks(status);
