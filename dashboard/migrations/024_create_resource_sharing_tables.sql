-- Migration: 024_create_resource_sharing_tables.sql
-- Purpose: Create resource sharing and allocation tables for multi-department resource management
-- Created: 2026-04-23

-- Department Resources テーブル: 各部署が保有するリソース情報
CREATE TABLE IF NOT EXISTS department_resources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
  resource_type TEXT NOT NULL,  -- cpu, memory, threads, api_calls, etc.
  total_allocated INTEGER NOT NULL,  -- 総配分量
  current_used INTEGER DEFAULT 0,  -- 現在使用量
  reserved INTEGER DEFAULT 0,  -- 予約量
  unit TEXT DEFAULT 'units',  -- 単位（cores, MB, count等）
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(department_id, resource_type)
);

-- Resource Allocations テーブル: リソース配分の詳細
CREATE TABLE IF NOT EXISTS resource_allocations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
  resource_type TEXT NOT NULL,  -- cpu, memory, threads, api_calls等
  amount INTEGER NOT NULL,  -- 配分量
  priority INTEGER DEFAULT 3,  -- 1=critical, 2=high, 3=normal, 4=low
  status TEXT DEFAULT 'pending',  -- pending, active, completed, revoked
  allocated_at TIMESTAMP,  -- 配分した日時
  expires_at TIMESTAMP,  -- 配分の有効期限（NULLで無期限）
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resource Requests テーブル: リソース要求履歴
CREATE TABLE IF NOT EXISTS resource_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
  resource_type TEXT NOT NULL,  -- cpu, memory, threads, api_calls等
  required_amount INTEGER NOT NULL,  -- 要求量
  reason TEXT,  -- 要求の理由
  status TEXT DEFAULT 'pending',  -- pending, approved, rejected, completed, cancelled
  approved_amount INTEGER,  -- 承認量（NULLの場合は未承認）
  approval_reason TEXT,  -- 承認/却下の理由
  approved_by TEXT,  -- 承認者
  requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  approved_at TIMESTAMP,  -- 承認日時
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_department_resources_department_id
  ON department_resources(department_id);
CREATE INDEX IF NOT EXISTS idx_department_resources_resource_type
  ON department_resources(resource_type);
CREATE INDEX IF NOT EXISTS idx_resource_allocations_department_id
  ON resource_allocations(department_id);
CREATE INDEX IF NOT EXISTS idx_resource_allocations_resource_type
  ON resource_allocations(resource_type);
CREATE INDEX IF NOT EXISTS idx_resource_allocations_status
  ON resource_allocations(status);
CREATE INDEX IF NOT EXISTS idx_resource_requests_department_id
  ON resource_requests(department_id);
CREATE INDEX IF NOT EXISTS idx_resource_requests_resource_type
  ON resource_requests(resource_type);
CREATE INDEX IF NOT EXISTS idx_resource_requests_status
  ON resource_requests(status);
