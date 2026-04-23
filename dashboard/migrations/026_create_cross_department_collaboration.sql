-- Migration: 026_create_cross_department_collaboration.sql
-- Purpose: Create cross-department collaboration tables (Task #2414)
--   - inter_department_requests: 部署間リクエスト (task_request / resource_request / skill_request)
--   - inter_department_task_allocations: リクエストに紐づくタスク共有割当
--   - inter_department_collaboration_log: コラボレーションのやり取りログ
-- Note: Task allocations reference the existing `tasks` table (plan referred to `dev_tasks`,
--       which does not exist in this schema; `tasks` is the canonical table per 014_create_tasks_table.sql).
-- Created: 2026-04-23

-- 1. 部署間リクエスト
CREATE TABLE IF NOT EXISTS inter_department_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requesting_department_id INTEGER NOT NULL REFERENCES department_instances(id) ON DELETE CASCADE,
    receiving_department_id INTEGER NOT NULL REFERENCES department_instances(id) ON DELETE CASCADE,
    request_type TEXT NOT NULL CHECK(request_type IN ('task_request', 'resource_request', 'skill_request')),
    priority INTEGER DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
    description TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'acknowledged', 'in_progress', 'completed', 'rejected')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(requesting_department_id, receiving_department_id, request_type, created_at)
);

CREATE INDEX IF NOT EXISTS idx_inter_dept_req_requesting
    ON inter_department_requests(requesting_department_id);
CREATE INDEX IF NOT EXISTS idx_inter_dept_req_receiving
    ON inter_department_requests(receiving_department_id);
CREATE INDEX IF NOT EXISTS idx_inter_dept_req_status
    ON inter_department_requests(status);

-- 2. タスク共有割当
CREATE TABLE IF NOT EXISTS inter_department_task_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES inter_department_requests(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    allocated_agent_id INTEGER REFERENCES agents(id),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'allocated', 'in_progress', 'completed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    completed_at TEXT,
    UNIQUE(request_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_inter_dept_alloc_request
    ON inter_department_task_allocations(request_id);
CREATE INDEX IF NOT EXISTS idx_inter_dept_alloc_task
    ON inter_department_task_allocations(task_id);
CREATE INDEX IF NOT EXISTS idx_inter_dept_alloc_status
    ON inter_department_task_allocations(status);

-- 3. コラボレーションログ
CREATE TABLE IF NOT EXISTS inter_department_collaboration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES inter_department_requests(id) ON DELETE CASCADE,
    collaboration_type TEXT CHECK(collaboration_type IN ('status_update', 'blocker_resolution', 'progress_note')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_inter_dept_collab_request
    ON inter_department_collaboration_log(request_id);
