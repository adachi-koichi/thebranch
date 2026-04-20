-- Add onboarding_completed flag to users table
ALTER TABLE users ADD COLUMN onboarding_completed INTEGER DEFAULT 0;
CREATE INDEX idx_users_onboarding_completed ON users(onboarding_completed);
