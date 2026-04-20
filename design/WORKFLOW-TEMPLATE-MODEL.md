# ワークフローテンプレート - データモデル設計

**タスク ID**: #2242  
**フェーズ**: 設計フェーズ  
**作成日**: 2026-04-20  
**バージョン**: v1.0

---

## 1. データモデル概要

ワークフローテンプレートシステムは、以下の 3 層構造で実装される：

```
層 1: テンプレート定義層
  └─ workflow_templates（メタデータ）
     ├─ wf_template_phases（フェーズ定義）
     └─ wf_template_tasks（タスク定義）

層 2: インスタンス化層
  └─ workflow_instances（インスタンス）
     ├─ workflow_instance_specialists（Specialist 割り当て）
     └─ wf_instance_nodes（フェーズ実行状態）

層 3: 実行層
  └─ dev_tasks（実際のタスク） ← 自動生成される
```

---

## 2. テーブル定義

### 2-1. workflow_templates（テンプレート）

**役割**: ワークフローテンプレートのメタデータを管理

```sql
CREATE TABLE IF NOT EXISTS workflow_templates (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL UNIQUE,              -- テンプレート名（例: "Product Launch"）
    description       TEXT,                              -- テンプレート説明
    category          TEXT,                              -- カテゴリ（'product', 'bug-fix', 'feature', 'devops'）
    version           INTEGER DEFAULT 1,                 -- バージョン
    status            TEXT DEFAULT 'draft'               -- draft / active / deprecated
                      CHECK(status IN ('draft', 'active', 'deprecated')),
    owner_id          INTEGER,                           -- テンプレート所有者（agents.id）
    organization_id   INTEGER,                           -- 所属組織（multi-tenancy 対応）
    phase_count       INTEGER DEFAULT 0,                 -- フェーズ数（キャッシュ）
    task_count        INTEGER DEFAULT 0,                 -- タスク総数（キャッシュ）
    estimated_hours   INTEGER,                           -- 全体見積もり時間
    tags              TEXT,                              -- JSON: ["tag1", "tag2"]
    config            TEXT,                              -- JSON: 追加設定（並列度制限等）
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    created_by        TEXT,                              -- 作成者（audit 用）
    updated_by        TEXT                               -- 最終更新者（audit 用）
);

CREATE INDEX IF NOT EXISTS idx_workflow_templates_status ON workflow_templates(status);
CREATE INDEX IF NOT EXISTS idx_workflow_templates_organization_id ON workflow_templates(organization_id);
```

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | テンプレート ID |
| name | TEXT NOT NULL UNIQUE | テンプレート名 |
| description | TEXT | テンプレート説明 |
| category | TEXT | カテゴリ分類 |
| version | INTEGER | バージョン |
| status | TEXT | ステータス（draft/active/deprecated） |
| owner_id | INTEGER | テンプレート所有者 ID |
| organization_id | INTEGER | 所属組織 ID |
| phase_count | INTEGER | フェーズ数（キャッシュ） |
| task_count | INTEGER | タスク総数（キャッシュ） |
| estimated_hours | INTEGER | 見積もり時間 |
| tags | TEXT | タグ（JSON） |
| config | TEXT | 設定情報（JSON） |
| created_at | TEXT | 作成日時 |
| updated_at | TEXT | 更新日時 |
| created_by | TEXT | 作成者 |
| updated_by | TEXT | 更新者 |

---

### 2-2. wf_template_phases（フェーズ定義）

**役割**: テンプレート内のフェーズ（段階）をメタデータ管理

```sql
CREATE TABLE IF NOT EXISTS wf_template_phases (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id       INTEGER NOT NULL REFERENCES workflow_templates(id),
    phase_key         TEXT NOT NULL,                     -- テンプレート内一意キー（'planning', 'dev', 'qa'）
    phase_order       INTEGER NOT NULL,                  -- 実行順序（1, 2, 3, ...）
    phase_label       TEXT NOT NULL,                     -- 表示名（"Planning Phase"）
    description       TEXT,                              -- フェーズ説明
    specialist_type   TEXT NOT NULL,                     -- 必要なロール（'pm', 'engineer', 'qa', 'devops'）
    specialist_count  INTEGER DEFAULT 1,                 -- このフェーズに割り当てる人数
    is_parallel       BOOLEAN DEFAULT 0,                 -- 前フェーズと並列実行可能か
    task_count        INTEGER DEFAULT 0,                 -- このフェーズのタスク数（キャッシュ）
    estimated_hours   INTEGER,                           -- フェーズ見積もり時間
    config            TEXT,                              -- JSON: 追加設定（approval_required 等）
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, phase_key),
    FOREIGN KEY(template_id) REFERENCES workflow_templates(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wf_template_phases_template_order 
    ON wf_template_phases(template_id, phase_order);
```

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | フェーズ ID |
| template_id | INTEGER FK | 親テンプレート ID |
| phase_key | TEXT NOT NULL | テンプレート内一意キー |
| phase_order | INTEGER NOT NULL | 実行順序 |
| phase_label | TEXT NOT NULL | 表示名 |
| description | TEXT | 説明 |
| specialist_type | TEXT NOT NULL | 必要なロール |
| specialist_count | INTEGER | 割り当て人数 |
| is_parallel | BOOLEAN | 並列実行可能フラグ |
| task_count | INTEGER | タスク数（キャッシュ） |
| estimated_hours | INTEGER | 見積もり時間 |
| config | TEXT | 追加設定（JSON） |
| created_at | TEXT | 作成日時 |
| updated_at | TEXT | 更新日時 |

---

### 2-3. wf_template_tasks（タスク定義）

**役割**: 各フェーズ内のタスクテンプレートを定義（自動生成時に参照）

```sql
CREATE TABLE IF NOT EXISTS wf_template_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id       INTEGER NOT NULL REFERENCES workflow_templates(id),
    phase_id          INTEGER NOT NULL REFERENCES wf_template_phases(id),
    task_key          TEXT NOT NULL,                     -- フェーズ内一意キー（'design-arch', 'implement-api'）
    task_title        TEXT NOT NULL,                     -- タスク表示名
    task_description  TEXT,                              -- タスク説明（プレースホルダ対応: {specialist_name} 等）
    category          TEXT,                              -- タスクカテゴリ（'design', 'implement', 'test'）
    priority          INTEGER DEFAULT 3,                 -- 優先度（1=高, 2=中, 3=低）
    estimated_hours   INTEGER,                           -- 見積もり時間
    depends_on_key    TEXT,                              -- 同一フェーズ内の依存タスクキー（NULL = 並列実行可能）
    acceptance_criteria TEXT,                            -- 受け入れ基準（Gherkin/テキスト）
    tags              TEXT,                              -- JSON: ["tag1", "tag2"]
    config            TEXT,                              -- JSON: 追加設定
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(phase_id, task_key),
    FOREIGN KEY(template_id) REFERENCES workflow_templates(id) ON DELETE CASCADE,
    FOREIGN KEY(phase_id) REFERENCES wf_template_phases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wf_template_tasks_phase 
    ON wf_template_tasks(phase_id, task_key);
```

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | タスク定義 ID |
| template_id | INTEGER FK | 親テンプレート ID |
| phase_id | INTEGER FK | 親フェーズ ID |
| task_key | TEXT NOT NULL | フェーズ内一意キー |
| task_title | TEXT NOT NULL | タスク表示名 |
| task_description | TEXT | 説明（プレースホルダ対応） |
| category | TEXT | タスクカテゴリ |
| priority | INTEGER | 優先度 |
| estimated_hours | INTEGER | 見積もり時間 |
| depends_on_key | TEXT | 依存タスクキー |
| acceptance_criteria | TEXT | 受け入れ基準 |
| tags | TEXT | タグ（JSON） |
| config | TEXT | 設定情報（JSON） |
| created_at | TEXT | 作成日時 |

---

### 2-4. workflow_instances（ワークフローインスタンス）

**役割**: テンプレートのインスタンス（実行単位）をメタデータ管理

```sql
CREATE TABLE IF NOT EXISTS workflow_instances (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id       INTEGER NOT NULL REFERENCES workflow_templates(id),
    name              TEXT NOT NULL,                     -- インスタンス名（"Product Launch #1"）
    status            TEXT DEFAULT 'pending'             -- pending / running / completed / failed / cancelled
                      CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    current_phase_key TEXT,                              -- 現在実行中のフェーズキー
    context           TEXT,                              -- JSON: Specialist 割り当て・カスタムパラメータ等
    created_by        TEXT,                              -- インスタンス作成者
    project_id        INTEGER,                           -- 関連プロジェクト ID
    organization_id   INTEGER,                           -- 所属組織 ID
    start_time        TEXT,                              -- 開始時刻
    end_time          TEXT,                              -- 終了時刻
    estimated_hours   INTEGER,                           -- 見積もり時間（テンプレートから継承）
    actual_hours      REAL,                              -- 実績時間（計算値）
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY(template_id) REFERENCES workflow_templates(id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_instances_template_status 
    ON workflow_instances(template_id, status);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_organization 
    ON workflow_instances(organization_id);
```

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | インスタンス ID |
| template_id | INTEGER FK | 親テンプレート ID |
| name | TEXT NOT NULL | インスタンス名 |
| status | TEXT | ステータス |
| current_phase_key | TEXT | 現在フェーズ |
| context | TEXT | メタデータ（JSON） |
| created_by | TEXT | 作成者 |
| project_id | INTEGER | プロジェクト ID |
| organization_id | INTEGER | 組織 ID |
| start_time | TEXT | 開始時刻 |
| end_time | TEXT | 終了時刻 |
| estimated_hours | INTEGER | 見積もり時間 |
| actual_hours | REAL | 実績時間 |
| created_at | TEXT | 作成日時 |
| updated_at | TEXT | 更新日時 |

---

### 2-5. workflow_instance_specialists（Specialist 割り当て）

**役割**: インスタンス化時に各フェーズに割り当てられた Specialist を記録

```sql
CREATE TABLE IF NOT EXISTS workflow_instance_specialists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id       INTEGER NOT NULL REFERENCES workflow_instances(id),
    phase_id          INTEGER NOT NULL REFERENCES wf_template_phases(id),
    phase_key         TEXT NOT NULL,                     -- フェーズキー（検索効率化）
    specialist_id     INTEGER NOT NULL,                  -- agents.id
    specialist_slug   TEXT NOT NULL,                     -- agents.slug（"em-alice" 等）
    specialist_name   TEXT NOT NULL,                     -- agents.name（表示用）
    specialist_role   TEXT NOT NULL,                     -- agents.role_type（"em", "engineer", "qa"）
    assigned_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, phase_key),
    FOREIGN KEY(instance_id) REFERENCES workflow_instances(id) ON DELETE CASCADE,
    FOREIGN KEY(phase_id) REFERENCES wf_template_phases(id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_instance_specialists_instance 
    ON workflow_instance_specialists(instance_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_specialists_specialist_id 
    ON workflow_instance_specialists(specialist_id);
```

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | 割り当て ID |
| instance_id | INTEGER FK | 親インスタンス ID |
| phase_id | INTEGER FK | フェーズ ID |
| phase_key | TEXT | フェーズキー |
| specialist_id | INTEGER | エージェント ID |
| specialist_slug | TEXT | エージェントスラッグ |
| specialist_name | TEXT | エージェント名 |
| specialist_role | TEXT | ロール |
| assigned_at | TEXT | 割り当て日時 |

---

### 2-6. wf_instance_nodes（フェーズ実行状態）

**役割**: インスタンス内の各フェーズの実行状態を管理

```sql
CREATE TABLE IF NOT EXISTS wf_instance_nodes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id       INTEGER NOT NULL REFERENCES workflow_instances(id),
    phase_id          INTEGER NOT NULL REFERENCES wf_template_phases(id),
    node_key          TEXT NOT NULL,                     -- ノードキー（"{instance_id}_{phase_key}"）
    status            TEXT DEFAULT 'waiting'             -- waiting / ready / running / completed / failed / skipped
                      CHECK(status IN ('waiting', 'ready', 'running', 'completed', 'failed', 'skipped')),
    task_ids          TEXT,                              -- JSON: [task_id1, task_id2, ...] このフェーズのタスク ID リスト
    started_at        TEXT,                              -- フェーズ開始時刻
    completed_at      TEXT,                              -- フェーズ完了時刻
    notes             TEXT,                              -- フェーズ実行ノート
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, phase_id),
    FOREIGN KEY(instance_id) REFERENCES workflow_instances(id) ON DELETE CASCADE,
    FOREIGN KEY(phase_id) REFERENCES wf_template_phases(id)
);

CREATE INDEX IF NOT EXISTS idx_wf_instance_nodes_instance_status 
    ON wf_instance_nodes(instance_id, status);
```

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | ノード ID |
| instance_id | INTEGER FK | インスタンス ID |
| phase_id | INTEGER FK | フェーズ ID |
| node_key | TEXT | ノードキー |
| status | TEXT | ステータス |
| task_ids | TEXT | タスク ID リスト（JSON） |
| started_at | TEXT | 開始時刻 |
| completed_at | TEXT | 完了時刻 |
| notes | TEXT | ノート |
| created_at | TEXT | 作成日時 |
| updated_at | TEXT | 更新日時 |

---

## 3. リレーション図（ER 図）

```
┌─────────────────────────────┐
│   workflow_templates        │
│ (id, name, status, ...)     │
└──────────┬──────────────────┘
           │ 1:N
           │
       ┌───┴────┬──────────────────────┐
       │         │                      │
       │         │                      │
   ┌───v──┐  ┌──v──────────────┐   ┌───v─────────────────┐
   │ wf_  │  │ wf_template_    │   │ workflow_           │
   │ temp │  │ phases          │   │ instances           │
   │ late │  │ (phase_order,   │   │ (template_id,       │
   │ _    │  │  specialist_    │   │  status,            │
   │ task │  │  type, ...)     │   │  context, ...)      │
   │ s    │  └──┬──────────────┘   │                     │
   │ (ta  │     │ 1:N               └───┬──────────┬─────┘
   │ sk   │     │                       │ 1:N      │
   │ key, │     │         ┌─────────────v──┐   ┌───v──────────────┐
   │ prio │     │         │ workflow_      │   │ wf_instance_     │
   │ ...)│     │         │ instance_      │   │ nodes            │
   └─────┘     │         │ specialists    │   │ (status:         │
               │         │ (specialist_   │   │  waiting/ready..│
               └─────────> id,            │   │  task_ids)      │
                          specialist_    │   └─────────────────┘
                          slug, ...)     │
                          └───────────────┘
```

---

## 4. データフロー（インスタンス化時）

```
ユーザー操作
  ↓
[テンプレート選択]
  ↓
workflow_templates を読み込む（id, name, phase_count, ...）
  ↓
[Specialist 割り当て UI]（ユーザーが phase_key ごとに specialist_id を指定）
  ↓
workflow_instances を作成（template_id, context={specialists: {...}}, status='pending'）
  ↓
wf_template_phases を読み込む（template_id, phase_order でソート）
  ↓
FOR EACH phase:
  ├─ workflow_instance_specialists を作成（specialist_id, specialist_slug, specialist_role）
  ├─ wf_instance_nodes を作成（status='waiting'）
  └─ wf_template_tasks を読み込み
     └─ FOR EACH task_def:
        ├─ dev_tasks を作成（title, description, assignee=specialist_slug）
        └─ wf_instance_nodes.task_ids に dev_tasks.id を追加
  ↓
  タスク依存関係を設定（task_dependencies テーブルに）
  ├─ フェーズ内依存（depends_on_key）
  └─ フェーズ間依存（前フェーズ → 次フェーズ）
  ↓
workflow_instances.status を 'running' に更新
  ↓
[インスタンス化完了] → dev_tasks でワークフロー実行開始
```

---

## 5. 主要な SQL クエリ（設計）

### 5-1. テンプレート一覧取得（フィルタリング対応）

```sql
SELECT 
    id, name, description, category, version, status,
    phase_count, task_count, estimated_hours
FROM workflow_templates
WHERE status = 'active'
  AND (organization_id = ? OR organization_id IS NULL)  -- multi-tenancy
ORDER BY created_at DESC
LIMIT 50;
```

### 5-2. テンプレート詳細取得（フェーズ・タスク情報含）

```sql
-- Template
SELECT id, name, description, version, status, estimated_hours
FROM workflow_templates
WHERE id = ?;

-- Phases
SELECT id, phase_order, phase_label, phase_key, specialist_type, 
       specialist_count, task_count, estimated_hours
FROM wf_template_phases
WHERE template_id = ?
ORDER BY phase_order ASC;

-- Tasks for each Phase
SELECT id, task_key, task_title, category, priority, estimated_hours, 
       depends_on_key, acceptance_criteria
FROM wf_template_tasks
WHERE phase_id = ?
ORDER BY task_key ASC;
```

### 5-3. インスタンス化（トランザクション）

```sql
BEGIN TRANSACTION;

-- 1. Instance 作成
INSERT INTO workflow_instances 
  (template_id, name, status, context, created_by, organization_id, created_at, updated_at)
VALUES (?, ?, 'pending', ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'));
-- → instance_id を取得

-- 2. Specialist 割り当て（context JSON から各 phase_key に対応する specialist_id を読み込み）
INSERT INTO workflow_instance_specialists 
  (instance_id, phase_id, phase_key, specialist_id, specialist_slug, specialist_name, specialist_role, assigned_at)
SELECT ?, id, phase_key, ?, (SELECT slug FROM agents WHERE id = ?), 
       (SELECT name FROM agents WHERE id = ?), 
       (SELECT role_type FROM agents WHERE id = ?),
       datetime('now','localtime')
FROM wf_template_phases
WHERE template_id = ?;

-- 3. Phase Node 作成
INSERT INTO wf_instance_nodes 
  (instance_id, phase_id, node_key, status, task_ids, created_at, updated_at)
SELECT ?, id, CONCAT(?, '_', phase_key), 'waiting', '[]', 
       datetime('now','localtime'), datetime('now','localtime')
FROM wf_template_phases
WHERE template_id = ?;

-- 4. Task 生成（フェーズごと）
-- [タスク生成ロジックは Python コードで実装]

COMMIT;
```

---

## 6. スキーマの拡張性

### 6-1. 将来の拡張ポイント

| 拡張項目 | 説明 |
|---|---|
| **テンプレート継承** | 既存テンプレートをベースに新しいテンプレートを派生作成 |
| **条件分岐フェーズ** | if-then-else フェーズ（前フェーズの結果により分岐） |
| **ダイナミック Specialist 割り当て** | AI による自動割り当て提案 |
| **テンプレート実績分析** | 平均実行時間・成功率等の統計情報 |
| **バージョン管理** | テンプレート変更の履歴・ロールバック機能 |

### 6-2. config カラムの拡張（JSON スキーマ）

```json
{
  "parallel_degree": 2,          // 最大並列フェーズ数
  "approval_required": false,    // 各フェーズ完了時に承認必須
  "auto_escalate_hours": 48,     // 指定時間超過時に自動エスカレーション
  "slack_notifications": true,   // Slack 通知有効化
  "custom_fields": {             // カスタム属性
    "product_category": "string",
    "priority": "enum"
  }
}
```

---

## 7. 制約・検証ルール

| ルール | 説明 |
|---|---|
| **Template 一意性** | template_name は unique（同一組織内） |
| **Phase 順序一意性** | template_id ごとに phase_order は一意で、1 から始まる連番 |
| **Phase キー一意性** | template_id ごとに phase_key は一意 |
| **Task キー一意性** | phase_id ごとに task_key は一意 |
| **Status 遷移制約** | instance status は定義された遷移パスのみ可能 |
| **Specialist 存在確認** | specialist_id は agents テーブルに存在 |
| **フェーズ依存性** | phase_order に基づいて段階的にフェーズを進行 |

---

## 8. インデックス戦略

```sql
-- テンプレート検索
CREATE INDEX idx_workflow_templates_status ON workflow_templates(status);
CREATE INDEX idx_workflow_templates_organization_id ON workflow_templates(organization_id);
CREATE INDEX idx_workflow_templates_category ON workflow_templates(category);

-- フェーズ検索
CREATE INDEX idx_wf_template_phases_template_order 
    ON wf_template_phases(template_id, phase_order);

-- タスク検索
CREATE INDEX idx_wf_template_tasks_phase ON wf_template_tasks(phase_id, task_key);

-- インスタンス検索
CREATE INDEX idx_workflow_instances_template_status 
    ON workflow_instances(template_id, status);
CREATE INDEX idx_workflow_instances_organization 
    ON workflow_instances(organization_id);
CREATE INDEX idx_workflow_instances_current_phase 
    ON workflow_instances(current_phase_key);

-- Specialist 検索
CREATE INDEX idx_workflow_instance_specialists_instance 
    ON workflow_instance_specialists(instance_id);
CREATE INDEX idx_workflow_instance_specialists_specialist_id 
    ON workflow_instance_specialists(specialist_id);

-- Instance Node 検索
CREATE INDEX idx_wf_instance_nodes_instance_status 
    ON wf_instance_nodes(instance_id, status);
```

---

## 9. マイグレーション戦略

### 9-1. 初期化 SQL（セットアップ）

`scripts/init_workflow_template_schema.sql` で以下を実行：

```sql
-- 1. テーブル作成（上記の CREATE TABLE ステートメント）
-- 2. インデックス作成
-- 3. サンプルデータ挿入（例: "Product Launch" テンプレート）
```

### 9-2. バージョン管理

`migration/` ディレクトリで管理：

```
migration/
  ├─ 001_init_workflow_template_schema.sql
  ├─ 002_add_organization_id.sql
  ├─ 003_add_wf_instance_nodes.sql
  └─ ...
```

---

## 参考資料

- [テンプレート定義サンプル](design/WORKFLOW-TEMPLATE-SAMPLES.md)（別ドキュメント）
- [既存技術設計（Phase 2）](docs/workflow-template-design.md)
- [BDD テスト仕様](features/workflow-template.feature)

---

*このドキュメントは タスク #2242 の設計フェーズにおけるデータモデル仕様です。*
