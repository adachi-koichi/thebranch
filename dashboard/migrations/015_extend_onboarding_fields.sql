-- オンボーディング進捗テーブルのパフォーマンス向上インデックス追加
CREATE INDEX IF NOT EXISTS idx_onboarding_dept_id
ON user_onboarding_progress(dept_id);

CREATE INDEX IF NOT EXISTS idx_onboarding_completed_at
ON user_onboarding_progress(completed_at);

CREATE INDEX IF NOT EXISTS idx_onboarding_user_id_current_step
ON user_onboarding_progress(user_id, current_step);
