-- Create user_onboarding_progress table
CREATE TABLE IF NOT EXISTS user_onboarding_progress (
    onboarding_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,

    -- Step 0: Vision Input
    vision_input TEXT,

    -- Step 1: AI Suggestion
    suggested_template_id TEXT,
    suggestion_reason TEXT,

    -- Step 2: Detailed Setup
    dept_id TEXT,
    dept_name TEXT,
    manager_name TEXT,
    members_count INTEGER,
    budget INTEGER,
    kpi TEXT,
    integrations TEXT,  -- JSON stored as TEXT

    -- Step 3: Initial Task Execution
    initial_tasks TEXT,  -- JSON stored as TEXT
    agent_status TEXT,  -- 'created', 'activated', 'running'

    -- Metadata
    current_step INTEGER NOT NULL DEFAULT 0,
    completed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (dept_id) REFERENCES departments(id)
);

-- Create indices
CREATE INDEX IF NOT EXISTS idx_user_onboarding_user_id ON user_onboarding_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_user_onboarding_current_step ON user_onboarding_progress(current_step);

-- Create trigger to update updated_at
CREATE TRIGGER IF NOT EXISTS update_user_onboarding_progress_timestamp
AFTER UPDATE ON user_onboarding_progress
BEGIN
    UPDATE user_onboarding_progress SET updated_at = CURRENT_TIMESTAMP
    WHERE onboarding_id = NEW.onboarding_id;
END;
