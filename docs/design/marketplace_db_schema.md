# AIエージェント マーケットプレイス DB スキーマ設計

**Document Version**: 1.0  
**Created**: 2026-04-26  
**Related Task**: #2494 Tech Lead: AIエージェントマーケットプレイス設計

---

## 1. 概要

THEBRANCH マーケットプレイスは、AIエージェントの発見・インストール・共有を実現する機能です。本ドキュメントでは、マーケットプレイス実現のための DB スキーマを定義します。

### 機能スコープ

- ✅ エージェント一覧・検索・フィルター
- ✅ エージェント詳細表示
- ✅ エージェントのインストール
- ✅ カテゴリ・タグによる分類
- ✅ 検索インデックス（FTS5）
- ✅ インストール履歴・使用統計

---

## 2. テーブル設計

### 2.1 marketplace_categories テーブル

**目的**: エージェントのカテゴリマスタ

```sql
CREATE TABLE marketplace_categories (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  icon_url TEXT,
  display_order INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**カラム説明**:
| カラム名 | 型 | 説明 |
|---|---|---|
| id | TEXT | カテゴリID（UUID） |
| name | TEXT | カテゴリ名（HR、Finance、Marketing等） |
| description | TEXT | カテゴリの説明 |
| icon_url | TEXT | カテゴリアイコンのURL |
| display_order | INTEGER | UI上の表示順序 |
| created_at | DATETIME | 作成日時 |
| updated_at | DATETIME | 更新日時 |

**初期データ例**:
- HR（人事）
- Finance（財務）
- Marketing（マーケティング）
- Sales（営業）
- Engineering（エンジニアリング）
- Support（カスタマーサポート）
- Legal（法務）

---

### 2.2 marketplace_agents テーブル

**目的**: マーケットプレイスに登録されたエージェント情報

```sql
CREATE TABLE marketplace_agents (
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
  rating REAL DEFAULT 0.0,  -- 1.0 ～ 5.0
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
```

**カラム説明**:
| カラム名 | 型 | 説明 |
|---|---|---|
| id | TEXT | エージェントID（UUID） |
| name | TEXT | エージェント名 |
| description | TEXT | 短い説明（1行） |
| detailed_description | TEXT | 詳細説明（Markdown対応） |
| category_id | TEXT | カテゴリID（FK） |
| publisher_id | TEXT | 公開者ID（FK） |
| version | TEXT | バージョン番号（セマンティックバージョニング） |
| icon_url | TEXT | アイコンURL |
| banner_url | TEXT | バナーURL（詳細ページ用） |
| capabilities | TEXT | JSON配列：提供機能のリスト |
| tags | TEXT | JSON配列：検索タグ |
| installation_count | INTEGER | インストール数 |
| rating | REAL | 平均評価スコア |
| review_count | INTEGER | レビュー数 |
| status | TEXT | ステータス（draft/published/archived） |
| visibility | TEXT | 公開範囲（private/team/public） |
| documentation_url | TEXT | ドキュメントURL |
| github_url | TEXT | GitHubリポジトリURL |
| support_url | TEXT | サポート連絡先URL |
| requirements | TEXT | JSON：システム要件、依存関係 |
| settings_schema | TEXT | JSON：設定フォーム用スキーマ |
| created_at | DATETIME | 作成日時 |
| updated_at | DATETIME | 更新日時 |
| published_at | DATETIME | 公開日時 |

---

### 2.3 marketplace_agent_releases テーブル

**目的**: エージェントのバージョン管理

```sql
CREATE TABLE marketplace_agent_releases (
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
```

**目的**: 複数バージョンの管理、ロールバック対応

---

### 2.4 marketplace_agent_installations テーブル

**目的**: インストール履歴・使用統計

```sql
CREATE TABLE marketplace_agent_installations (
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
```

---

### 2.5 marketplace_agent_reviews テーブル

**目的**: エージェントへのレビュー・フィードバック

```sql
CREATE TABLE marketplace_agent_reviews (
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
```

---

### 2.6 marketplace_agent_features テーブル

**目的**: エージェント機能の詳細定義（正規化）

```sql
CREATE TABLE marketplace_agent_features (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  
  feature_name TEXT NOT NULL,
  feature_description TEXT,
  icon_url TEXT,
  
  display_order INTEGER DEFAULT 0,
  
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (agent_id) REFERENCES marketplace_agents(id)
);
```

**用途**: capabilities の JSON ネストを回避し、機能情報を個別に管理

---

### 2.7 marketplace_searches テーブル

**目的**: 検索クエリ・人気検索の追跡（オプション）

```sql
CREATE TABLE marketplace_searches (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  query TEXT NOT NULL,
  result_count INTEGER,
  
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 3. 検索インデックス設計

### 3.1 FTS5（Full Text Search）テーブル

```sql
CREATE VIRTUAL TABLE marketplace_agents_fts USING fts5(
  name,
  description,
  detailed_description,
  tags,
  capabilities,
  content=marketplace_agents,
  content_rowid=id
);
```

**用途**:
- テキスト検索（名前、説明、タグ）
- 高速フルテキスト検索を実現

**トリガー**: INSERT/UPDATE/DELETE 時に FTS テーブルを同期

---

### 3.2 通常インデックス

```sql
CREATE INDEX idx_marketplace_agents_category_id 
  ON marketplace_agents(category_id);

CREATE INDEX idx_marketplace_agents_publisher_id 
  ON marketplace_agents(publisher_id);

CREATE INDEX idx_marketplace_agents_status_visibility 
  ON marketplace_agents(status, visibility);

CREATE INDEX idx_marketplace_agents_installation_count 
  ON marketplace_agents(installation_count DESC);

CREATE INDEX idx_marketplace_agents_rating 
  ON marketplace_agents(rating DESC);

CREATE INDEX idx_marketplace_agent_installations_user_id 
  ON marketplace_agent_installations(user_id);

CREATE INDEX idx_marketplace_agent_installations_agent_id 
  ON marketplace_agent_installations(agent_id);

CREATE INDEX idx_marketplace_agent_reviews_agent_id 
  ON marketplace_agent_reviews(agent_id);

CREATE INDEX idx_marketplace_searches_created_at 
  ON marketplace_searches(created_at DESC);
```

---

## 4. リレーションシップ図

```
marketplace_categories (カテゴリマスタ)
  │
  └─→ marketplace_agents (エージェント)
        │
        ├─→ marketplace_agent_releases (バージョン管理)
        ├─→ marketplace_agent_installations (インストール履歴)
        ├─→ marketplace_agent_reviews (レビュー)
        └─→ marketplace_agent_features (機能詳細)

users (ユーザー)
  ├─→ marketplace_agents (publisher_id)
  ├─→ marketplace_agent_installations (user_id)
  ├─→ marketplace_agent_reviews (user_id)
  └─→ marketplace_searches (user_id)
```

---

## 5. 設計のポイント

### 5.1 スケーラビリティ
- **UUID**: テーブル増加に対応する一意な識別子
- **インデックス**: カテゴリ、ステータス、評価による高速検索
- **FTS5**: 大規模なテキスト検索に対応

### 5.2 セキュリティ
- **visibility**: private（自分のみ）/team（チーム）/public（全員）で公開範囲を制限
- **status**: draft→published の公開フロー管理
- **publisher_id**: 所有者の追跡

### 5.3 拡張性
- **JSON カラム**: capabilities、tags、requirements、settings_schema を JSON で保存
  - フロントエンド側で解析可能
  - スキーマ変更なしで柔軟に拡張
- **features テーブル**: 将来的に複雑な機能情報が必要な場合は個別テーブル化可能

### 5.4 分析・改善
- **installation_count**: 人気度
- **rating / review_count**: 品質指標
- **execution_count / success_count**: 使用実績
- **marketplace_searches**: ユーザー検索行動の分析

---

## 6. マイグレーション実装順序

```
1. marketplace_categories テーブル作成
2. marketplace_agents テーブル作成
3. marketplace_agent_releases テーブル作成
4. marketplace_agent_installations テーブル作成
5. marketplace_agent_reviews テーブル作成
6. marketplace_agent_features テーブル作成
7. marketplace_searches テーブル作成
8. FTS5 仮想テーブル作成 + トリガー定義
9. インデックス作成
10. 初期データ挿入（カテゴリ）
```

---

## 7. 次フェーズ

**API 設計**: `marketplace_api_design.md`
- GET /api/marketplace/agents
- GET /api/marketplace/agents/{id}
- POST /api/marketplace/agents/{id}/install

**フロントエンド設計**: `marketplace_frontend_design.md`
- マーケットプレイス一覧ページ
- エージェント詳細ページ
