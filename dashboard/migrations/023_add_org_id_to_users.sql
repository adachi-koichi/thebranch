-- Add org_id support for multi-tenant architecture
-- Adds organization_id reference to users and sessions tables

-- Create organizations table if not exists
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add org_id column to users table
ALTER TABLE users ADD COLUMN org_id TEXT DEFAULT 'default';

-- Create default organization if it doesn't exist
INSERT OR IGNORE INTO organizations (id, name, slug) VALUES ('default', 'Default Organization', 'default');

-- Add foreign key reference (SQLite doesn't support direct ALTER, so we use a constraint)
CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);

-- Add org_id to sessions table for context tracking
ALTER TABLE sessions ADD COLUMN org_id TEXT;

-- Update sessions to include org_id from users
UPDATE sessions SET org_id = (SELECT org_id FROM users WHERE users.id = sessions.user_id);

CREATE INDEX IF NOT EXISTS idx_sessions_org_id ON sessions(org_id);

-- Create indexes for multi-tenant queries
CREATE INDEX IF NOT EXISTS idx_users_org_username ON users(org_id, username);
CREATE INDEX IF NOT EXISTS idx_users_org_email ON users(org_id, email);
