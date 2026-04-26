-- Migration: 034_create_marketplace_tables
-- Date: 2026-04-26
-- Purpose: Create marketplace database tables and indexes

-- 1. marketplace_categories テーブル
CREATE TABLE IF NOT EXISTS marketplace_categories (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  icon_url TEXT,
  display_order INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. marketplace_agents テーブル
CREATE TABLE IF NOT EXISTS marketplace_agents (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  detailed_description TEXT,
  category_id TEXT NOT NULL,
  publisher_id TEXT NOT NULL,
  version TEXT DEFAULT '1.0.0',
  icon_url TEXT,
  banner_url TEXT,

  -- 機能・スキル
  capabilities TEXT,  -- JSON: ["task_automation", "analysis", ...]
  tags TEXT,          -- JSON: ["productivity", "analytics", ...]

  -- 統計情報
  installation_count INTEGER DEFAULT 0,
  rating REAL DEFAULT 0.0,
  review_count INTEGER DEFAULT 0,

  -- ステータス
  status TEXT DEFAULT 'draft',  -- draft, published, archived
  visibility TEXT DEFAULT 'private',  -- private, team, public

  -- リンク・リソース
  documentation_url TEXT,
  github_url TEXT,
  support_url TEXT,

  -- メタデータ
  requirements TEXT,  -- JSON: システム要件
  settings_schema TEXT,  -- JSON: 設定スキーマ

  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  published_at DATETIME,

  FOREIGN KEY (category_id) REFERENCES marketplace_categories(id),
  FOREIGN KEY (publisher_id) REFERENCES users(id)
);

-- 3. marketplace_agent_releases テーブル
CREATE TABLE IF NOT EXISTS marketplace_agent_releases (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  version TEXT NOT NULL,
  release_notes TEXT,
  package_url TEXT NOT NULL,
  checksum TEXT,

  installation_count INTEGER DEFAULT 0,
  download_count INTEGER DEFAULT 0,

  status TEXT DEFAULT 'active',  -- active, deprecated, yanked

  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  published_at DATETIME,

  FOREIGN KEY (agent_id) REFERENCES marketplace_agents(id),
  UNIQUE(agent_id, version)
);

-- 4. marketplace_agent_installations テーブル
CREATE TABLE IF NOT EXISTS marketplace_agent_installations (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  organization_id TEXT,
  release_version TEXT NOT NULL,

  -- インストール情報
  installed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  uninstalled_at DATETIME,
  last_used_at DATETIME,

  -- 設定
  configuration TEXT,  -- JSON：インストール時の設定

  -- ステータス
  status TEXT DEFAULT 'active',  -- active, suspended, uninstalled

  -- 統計
  execution_count INTEGER DEFAULT 0,
  success_count INTEGER DEFAULT 0,
  error_count INTEGER DEFAULT 0,
  avg_execution_time REAL,  -- ミリ秒

  FOREIGN KEY (agent_id) REFERENCES marketplace_agents(id),
  FOREIGN KEY (user_id) REFERENCES users(id),
  UNIQUE(agent_id, user_id, organization_id)
);

-- 5. marketplace_agent_reviews テーブル
CREATE TABLE IF NOT EXISTS marketplace_agent_reviews (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  user_id TEXT NOT NULL,

  rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
  title TEXT,
  comment TEXT,

  helpful_count INTEGER DEFAULT 0,

  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (agent_id) REFERENCES marketplace_agents(id),
  FOREIGN KEY (user_id) REFERENCES users(id),
  UNIQUE(agent_id, user_id)
);

-- 6. marketplace_agent_features テーブル
CREATE TABLE IF NOT EXISTS marketplace_agent_features (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,

  feature_name TEXT NOT NULL,
  feature_description TEXT,
  icon_url TEXT,

  display_order INTEGER DEFAULT 0,

  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (agent_id) REFERENCES marketplace_agents(id)
);

-- 7. marketplace_searches テーブル
CREATE TABLE IF NOT EXISTS marketplace_searches (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  query TEXT NOT NULL,
  result_count INTEGER,

  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 8. FTS5 仮想テーブル
CREATE VIRTUAL TABLE IF NOT EXISTS marketplace_agents_fts USING fts5(
  name,
  description,
  detailed_description,
  tags,
  capabilities,
  content=marketplace_agents,
  content_rowid=id
);

-- 9. FTS トリガー - INSERT
CREATE TRIGGER IF NOT EXISTS marketplace_agents_ai AFTER INSERT ON marketplace_agents BEGIN
  INSERT INTO marketplace_agents_fts(rowid, name, description, detailed_description, tags, capabilities)
  VALUES (new.id, new.name, new.description, new.detailed_description, new.tags, new.capabilities);
END;

-- FTS トリガー - DELETE
CREATE TRIGGER IF NOT EXISTS marketplace_agents_ad AFTER DELETE ON marketplace_agents BEGIN
  INSERT INTO marketplace_agents_fts(marketplace_agents_fts, rowid, name, description, detailed_description, tags, capabilities)
  VALUES('delete', old.id, old.name, old.description, old.detailed_description, old.tags, old.capabilities);
END;

-- FTS トリガー - UPDATE
CREATE TRIGGER IF NOT EXISTS marketplace_agents_au AFTER UPDATE ON marketplace_agents BEGIN
  INSERT INTO marketplace_agents_fts(marketplace_agents_fts, rowid, name, description, detailed_description, tags, capabilities)
  VALUES('delete', old.id, old.name, old.description, old.detailed_description, old.tags, old.capabilities);
  INSERT INTO marketplace_agents_fts(rowid, name, description, detailed_description, tags, capabilities)
  VALUES (new.id, new.name, new.description, new.detailed_description, new.tags, new.capabilities);
END;

-- 10. インデックス作成
CREATE INDEX IF NOT EXISTS idx_marketplace_agents_category_id
  ON marketplace_agents(category_id);

CREATE INDEX IF NOT EXISTS idx_marketplace_agents_publisher_id
  ON marketplace_agents(publisher_id);

CREATE INDEX IF NOT EXISTS idx_marketplace_agents_status_visibility
  ON marketplace_agents(status, visibility);

CREATE INDEX IF NOT EXISTS idx_marketplace_agents_installation_count
  ON marketplace_agents(installation_count DESC);

CREATE INDEX IF NOT EXISTS idx_marketplace_agents_rating
  ON marketplace_agents(rating DESC);

CREATE INDEX IF NOT EXISTS idx_marketplace_agent_installations_user_id
  ON marketplace_agent_installations(user_id);

CREATE INDEX IF NOT EXISTS idx_marketplace_agent_installations_agent_id
  ON marketplace_agent_installations(agent_id);

CREATE INDEX IF NOT EXISTS idx_marketplace_agent_reviews_agent_id
  ON marketplace_agent_reviews(agent_id);

CREATE INDEX IF NOT EXISTS idx_marketplace_searches_created_at
  ON marketplace_searches(created_at DESC);

-- 11. 初期データ挿入（カテゴリ）
INSERT OR IGNORE INTO marketplace_categories (id, name, description, display_order) VALUES
  ('cat-001', 'HR', '人事・採用・人材管理', 0),
  ('cat-002', 'Finance', '財務・会計・請求', 1),
  ('cat-003', 'Marketing', 'マーケティング・広告・分析', 2),
  ('cat-004', 'Sales', '営業・CRM・リード管理', 3),
  ('cat-005', 'Engineering', 'エンジニアリング・開発・DevOps', 4),
  ('cat-006', 'Support', 'カスタマーサポート・チケット管理', 5),
  ('cat-007', 'Legal', '法務・契約・コンプライアンス', 6),
  ('cat-008', 'Operations', 'オペレーション・プロセス管理', 7),
  ('cat-009', 'Analytics', 'データ分析・ビジネスインテリジェンス', 8),
  ('cat-010', 'Communication', 'コミュニケーション・コラボレーション', 9);
