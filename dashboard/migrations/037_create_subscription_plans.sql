-- Migration: 037_create_subscription_plans.sql
-- Purpose: サブスクリプション・課金プラン基盤 (Task #2503)
--   - subscription_plans:    プランマスター（free / starter / pro / enterprise）
--   - user_subscriptions:    ユーザーの現在の契約
--   - subscription_events:   契約変更履歴・Stripe webhook 受け口
-- Created: 2026-04-30

CREATE TABLE IF NOT EXISTS subscription_plans (
    code              TEXT PRIMARY KEY,
    -- code: 'free' | 'starter' | 'pro' | 'enterprise'
    name              TEXT NOT NULL,
    tagline           TEXT,
    price_jpy         INTEGER NOT NULL DEFAULT 0,
    -- 月額（円）。enterprise は -1 (要相談)
    billing_period    TEXT NOT NULL DEFAULT 'monthly'
        CHECK(billing_period IN ('monthly', 'yearly', 'custom')),
    max_departments   INTEGER NOT NULL DEFAULT 1,
    max_agents        INTEGER NOT NULL DEFAULT 3,
    max_workflows     INTEGER NOT NULL DEFAULT 5,
    max_chat_messages_per_day INTEGER NOT NULL DEFAULT 50,
    features_json     TEXT NOT NULL DEFAULT '[]',
    -- 公開機能の配列 (UI バッジ用): ["custom_roles","priority_support",...]
    sort_order        INTEGER NOT NULL DEFAULT 0,
    is_public         INTEGER NOT NULL DEFAULT 1,
    -- 0: 非公開、1: 料金ページに表示
    stripe_price_id   TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS user_subscriptions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT NOT NULL,
    plan_code         TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('trialing', 'active', 'past_due', 'cancelled', 'paused')),
    started_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    current_period_start TEXT,
    current_period_end   TEXT,
    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
    cancelled_at      TEXT,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (plan_code) REFERENCES subscription_plans(code)
);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status  ON user_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_plan    ON user_subscriptions(plan_code);

CREATE TABLE IF NOT EXISTS subscription_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT,
    subscription_id   INTEGER,
    event_type        TEXT NOT NULL,
    -- event_type: 'subscribed','upgraded','downgraded','cancelled','renewed',
    --             'payment_succeeded','payment_failed','webhook'
    from_plan         TEXT,
    to_plan           TEXT,
    payload_json      TEXT,
    source            TEXT NOT NULL DEFAULT 'app'
        CHECK(source IN ('app', 'admin', 'stripe', 'system')),
    created_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_subscription_events_user      ON subscription_events(user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_events_type      ON subscription_events(event_type);
CREATE INDEX IF NOT EXISTS idx_subscription_events_created   ON subscription_events(created_at DESC);

-- 初期プランデータ
INSERT OR IGNORE INTO subscription_plans
    (code, name, tagline, price_jpy, billing_period, max_departments, max_agents,
     max_workflows, max_chat_messages_per_day, features_json, sort_order, is_public)
VALUES
    ('free',       'Free',       '個人で試せる無料枠',                       0,      'monthly',   1,  3,  5,    50,
     '["1部署","3エージェント","5ワークフロー","コミュニティサポート"]', 1, 1),
    ('starter',    'Starter',    '小規模チーム向け',                          2980,   'monthly',   3,  10, 20,   500,
     '["3部署","10エージェント","20ワークフロー","メールサポート","基本RBAC"]', 2, 1),
    ('pro',        'Pro',        '本格運用向け（推奨）',                      9800,   'monthly',   10, 50, 100,  5000,
     '["10部署","50エージェント","100ワークフロー","優先サポート","カスタムロール","監査ログ","API アクセス"]', 3, 1),
    ('enterprise', 'Enterprise', '大規模組織向け（要相談）',                  -1,     'custom',    999,999,999, 999999,
     '["無制限部署","無制限エージェント","SSO/SAML","SLA保証","専任CSM","オンプレミス対応"]', 4, 1);
