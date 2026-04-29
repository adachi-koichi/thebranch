-- Migration 038: サブスクリプション・課金管理テーブル作成 (Task #2548 Phase 1)
-- Purpose: Free/Pro プラン管理の基盤テーブル

-- マスタテーブル: プラン定義
CREATE TABLE IF NOT EXISTS subscription_plans (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    price_jpy INTEGER NOT NULL DEFAULT 0,
    is_public INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 999,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 初期データ: プランマスタ
INSERT OR IGNORE INTO subscription_plans (id, code, name, description, price_jpy, is_public, sort_order) VALUES
    ('plan-free', 'free', 'Free', 'Free plan - 3 agents, 1000 API calls/month', 0, 1, 1),
    ('plan-starter', 'starter', 'Starter', 'Starter plan - 10 agents, 10K API calls/month', 2980, 1, 2),
    ('plan-pro', 'pro', 'Pro', 'Pro plan - 50 agents, 1M API calls/month', 9900, 1, 3),
    ('plan-enterprise', 'enterprise', 'Enterprise', 'Enterprise plan - unlimited', -1, 1, 4);

-- ユーザーサブスクリプション管理テーブル
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    plan_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',

    current_period_start DATETIME NOT NULL,
    current_period_end DATETIME NOT NULL,
    canceled_at DATETIME,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_code) REFERENCES subscription_plans(code)
);

-- イベント記録テーブル: プラン変更履歴
CREATE TABLE IF NOT EXISTS subscription_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    from_plan TEXT,
    to_plan TEXT,
    source TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (subscription_id) REFERENCES user_subscriptions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON user_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_plan_code ON user_subscriptions(plan_code);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_current_period_end ON user_subscriptions(current_period_end);
CREATE INDEX IF NOT EXISTS idx_subscription_events_user_id ON subscription_events(user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_events_subscription_id ON subscription_events(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_events_event_type ON subscription_events(event_type);
