-- Migration 026: Create TOTP Secrets Table for 2FA
-- Task #2754: 2FA Implementation

CREATE TABLE totp_secrets (
  id TEXT PRIMARY KEY,
  user_id TEXT UNIQUE NOT NULL,
  secret TEXT NOT NULL,
  backup_codes TEXT NOT NULL,
  is_enabled INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  enabled_at DATETIME,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_totp_secrets_user_id ON totp_secrets(user_id);
