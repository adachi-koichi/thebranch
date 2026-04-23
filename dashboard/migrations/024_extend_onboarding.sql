-- Migration 024: Extend onboarding - Add onboarding_completed flag and onboarding_state table

-- Step 1: Add onboarding_completed flag to users table
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0;

-- Step 2: Create onboarding_state table to track wizard progress
CREATE TABLE IF NOT EXISTS onboarding_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    current_step INTEGER DEFAULT 1,
    organization_type TEXT,
    department_choice TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_onboarding_state_user_id ON onboarding_state(user_id);
