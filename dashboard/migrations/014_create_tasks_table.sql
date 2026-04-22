-- 오직보드 초기 작업을 위한 tasks 테이블 생성
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    assigned_to TEXT,
    budget REAL DEFAULT 0.0,
    deadline TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX idx_tasks_department_id ON tasks(department_id);
CREATE INDEX idx_tasks_status ON tasks(status);

CREATE TRIGGER update_tasks_timestamp
AFTER UPDATE ON tasks
BEGIN
    UPDATE tasks SET updated_at = datetime('now','localtime')
    WHERE id = NEW.id;
END;
