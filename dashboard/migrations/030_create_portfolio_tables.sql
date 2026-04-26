-- ポートフォリオ管理機能の基盤テーブル
-- 作成日: 2026-04-26

-- ポートフォリオ本体（ユーザーの組織・部門群をひとまとめに管理）
CREATE TABLE IF NOT EXISTS portfolios (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6)))),
    org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'draft')),
    visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'org', 'public')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ポートフォリオと部門の紐付け
CREATE TABLE IF NOT EXISTS portfolio_departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member' CHECK (role IN ('lead', 'member', 'observer')),
    added_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (portfolio_id, department_id)
);

-- ポートフォリオのKPI・パフォーマンスメトリクス
CREATE TABLE IF NOT EXISTS portfolio_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL,
    metric_value REAL,
    metric_unit TEXT,
    period TEXT,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ポートフォリオのスナップショット（定期保存用）
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    snapshot_data TEXT NOT NULL,
    snapshot_type TEXT NOT NULL DEFAULT 'manual' CHECK (snapshot_type IN ('manual', 'scheduled', 'milestone')),
    label TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- タグ・カテゴリ付け
CREATE TABLE IF NOT EXISTS portfolio_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    UNIQUE (portfolio_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_portfolios_org_id ON portfolios(org_id);
CREATE INDEX IF NOT EXISTS idx_portfolios_owner ON portfolios(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_departments_portfolio ON portfolio_departments(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_metrics_portfolio ON portfolio_metrics(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_portfolio ON portfolio_snapshots(portfolio_id);
