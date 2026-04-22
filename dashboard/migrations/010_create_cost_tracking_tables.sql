-- コスト追跡テーブル群
-- APIコスト・予算管理・アラート機能

CREATE TABLE IF NOT EXISTS api_calls (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id          INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    agent_id               INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    api_provider           TEXT NOT NULL CHECK(api_provider IN ('claude', 'openai', 'other')),
    model_name             TEXT,
    input_tokens           INTEGER NOT NULL,
    output_tokens          INTEGER NOT NULL,
    cache_read_tokens      INTEGER DEFAULT 0,
    cache_creation_tokens  INTEGER DEFAULT 0,
    cost_usd               REAL NOT NULL,
    status                 TEXT DEFAULT 'completed' CHECK(status IN ('pending', 'completed', 'failed')),
    error_message          TEXT,
    request_timestamp      INTEGER NOT NULL,
    created_at             TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_api_calls_dept_timestamp ON api_calls(department_id, request_timestamp);
CREATE INDEX IF NOT EXISTS idx_api_calls_agent_timestamp ON api_calls(agent_id, request_timestamp);
CREATE INDEX IF NOT EXISTS idx_api_calls_created_at ON api_calls(created_at);

CREATE TABLE IF NOT EXISTS cost_records (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id           INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    year                    INTEGER NOT NULL,
    month                   INTEGER NOT NULL,
    total_cost_usd          REAL NOT NULL,
    api_call_count          INTEGER NOT NULL,
    failed_call_count       INTEGER DEFAULT 0,
    average_cost_per_call   REAL GENERATED ALWAYS AS (
        CASE WHEN api_call_count > 0 THEN total_cost_usd / api_call_count ELSE 0 END
    ) STORED,
    top_model               TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(department_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_cost_records_dept_year_month ON cost_records(department_id, year, month);
CREATE INDEX IF NOT EXISTS idx_cost_records_created_at ON cost_records(created_at);

CREATE TABLE IF NOT EXISTS monthly_budgets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id       INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    year                INTEGER NOT NULL,
    month               INTEGER NOT NULL,
    budget_usd          REAL NOT NULL,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(department_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_monthly_budgets_dept ON monthly_budgets(department_id);
CREATE INDEX IF NOT EXISTS idx_monthly_budgets_year_month ON monthly_budgets(year, month);

CREATE TABLE IF NOT EXISTS cost_alerts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id       INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    alert_type          TEXT NOT NULL CHECK(alert_type IN ('budget_warning', 'budget_exceeded', 'anomaly')),
    threshold_percent   REAL,
    current_cost_usd    REAL NOT NULL,
    budget_usd          REAL NOT NULL,
    message             TEXT NOT NULL,
    status              TEXT DEFAULT 'unresolved' CHECK(status IN ('unresolved', 'resolved', 'ignored')),
    resolved_at         TEXT,
    resolved_by         TEXT,
    resolution_note     TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_cost_alerts_dept_created ON cost_alerts(department_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_status ON cost_alerts(status, created_at DESC);
