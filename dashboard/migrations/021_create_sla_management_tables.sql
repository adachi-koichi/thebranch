-- Migration 021: SLA Management Tables
-- Purpose: AIエージェントのSLA管理・サービス品質保証自動化機能

-- SLAポリシー定義テーブル
CREATE TABLE IF NOT EXISTS sla_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  response_time_limit_ms INTEGER NOT NULL,
  uptime_percentage REAL NOT NULL,
  error_rate_limit REAL NOT NULL,
  enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SLAメトリクス記録テーブル
CREATE TABLE IF NOT EXISTS sla_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  policy_id INTEGER NOT NULL,
  response_time_ms INTEGER,
  uptime_percentage REAL,
  error_rate REAL,
  measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(policy_id) REFERENCES sla_policies(id) ON DELETE CASCADE
);

-- SLA違反検出テーブル
CREATE TABLE IF NOT EXISTS sla_violations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  policy_id INTEGER NOT NULL,
  metric_id INTEGER NOT NULL,
  violation_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  details TEXT,
  alert_sent BOOLEAN DEFAULT FALSE,
  resolved_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(policy_id) REFERENCES sla_policies(id) ON DELETE CASCADE,
  FOREIGN KEY(metric_id) REFERENCES sla_metrics(id) ON DELETE CASCADE
);

-- インデックス作成（メトリクス検索・違反追跡の最適化）
CREATE INDEX IF NOT EXISTS idx_sla_metrics_policy_id ON sla_metrics(policy_id);
CREATE INDEX IF NOT EXISTS idx_sla_metrics_measured_at ON sla_metrics(measured_at);
CREATE INDEX IF NOT EXISTS idx_sla_violations_policy_id ON sla_violations(policy_id);
CREATE INDEX IF NOT EXISTS idx_sla_violations_created_at ON sla_violations(created_at);
