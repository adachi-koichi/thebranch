-- APIキー管理テーブル
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    created_by TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME,
    expires_at DATETIME,
    is_active BOOLEAN DEFAULT 1,
    rate_limit_per_minute INTEGER DEFAULT 100,
    description TEXT,
    FOREIGN KEY (org_id) REFERENCES organizations(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- APIキー使用履歴
CREATE TABLE IF NOT EXISTS api_key_usage (
    id TEXT PRIMARY KEY,
    api_key_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    user_agent TEXT,
    error_message TEXT,
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
);

-- APIキー権限設定
CREATE TABLE IF NOT EXISTS api_key_permissions (
    id TEXT PRIMARY KEY,
    api_key_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    action TEXT NOT NULL,
    UNIQUE(api_key_id, resource_type, action),
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_api_keys_org_id ON api_keys(org_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_created_by ON api_keys(created_by);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_api_key_id ON api_key_usage(api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_timestamp ON api_key_usage(timestamp);
CREATE INDEX IF NOT EXISTS idx_api_key_permissions_api_key_id ON api_key_permissions(api_key_id);
