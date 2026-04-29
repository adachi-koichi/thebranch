# BDD業務フロー データモデル設計書

**対象システム**: AI Orchestrator × task-manager-sqlite  
**バージョン**: 1.0  
**作成日**: 2026-04-19

---

## 目次

1. [概要](#概要)
2. [SQLite スキーマ設計](#sqlite-スキーマ設計)
3. [KuzuDB グラフスキーマ](#kuzudb-グラフスキーマ)
4. [テーブル間の関連性](#テーブル間の関連性)
5. [ステータス遷移と制約](#ステータス遷移と制約)
6. [整合性確認 (task-manager-sqlite との統合)](#整合性確認)

---

## 概要

### 背景

AI Orchestrator の業務フロー管理を **BDD ベース** に統一するため、SQLite + KuzuDB ハイブリッドデータモデルを設計する。

**主な目標:**
- Gherkin Scenario ← → SQLite テーブル の対応付け
- ワークフロー定義（.feature）→ インスタンス化（SQLite）→ 実行監視（KuzuDB グラフ）のチェーン
- task-manager-sqlite の既存機能との後方互換性維持

### 概念マッピング

| BDD 層 | SQLite テーブル | 用途 |
|--------|----------------|------|
| **Workflow Template** | `workflow_templates` | テンプレート定義・再利用 |
| **Workflow Instance** | `workflow_instances` | プロジェクト実行インスタンス |
| **Phase** | `workflow_phases` | フェーズ実行状態 |
| **Task** | `dev_tasks` (拡張) | 単位タスク・DAG依存関係 |
| **Agent Assignment** | `agent_assignments` (新規) | ロール割り当て・権限 |

---

## SQLite スキーマ設計

### テーブル 1: workflow_templates

**用途**: BDD Feature ファイル → テンプレート定義のマッピング

```sql
CREATE TABLE workflow_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  feature_file TEXT,
  description TEXT,
  version TEXT DEFAULT '1.0',
  phase_definitions TEXT NOT NULL,  -- JSON: フェーズ定義（5層）
  role_assignments TEXT,             -- JSON: ロール割り当て
  status TEXT CHECK(status IN ('draft', 'active', 'archived')) DEFAULT 'draft',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by TEXT,
  CONSTRAINT valid_version CHECK (version LIKE '%.%')
);

-- インデックス
CREATE UNIQUE INDEX idx_workflow_templates_name ON workflow_templates(name);
CREATE INDEX idx_workflow_templates_status ON workflow_templates(status);
```

**phase_definitions JSON 構造:**
```json
[
  {
    "phase_id": 1,
    "name": "Setup",
    "sequence": 1,
    "description": "環境準備・初期化",
    "timeout_minutes": 30,
    "role": "orchestrator",
    "required_fields": ["project", "repository_url"]
  },
  {
    "phase_id": 2,
    "name": "Planning",
    "sequence": 2,
    "description": "要件定義・計画",
    "timeout_minutes": 60,
    "role": "EM",
    "dependencies": [1],
    "required_fields": ["design_doc"]
  },
  ...
]
```

**role_assignments JSON 構造:**
```json
{
  "orchestrator": ["Setup", "Completion"],
  "EM": ["Planning", "Implementation"],
  "Engineer": ["Implementation"],
  "QA": ["Verification"],
  "Admin": ["*"]
}
```

---

### テーブル 2: workflow_instances

**用途**: ワークフロー実行インスタンス・プロジェクト単位の管理

```sql
CREATE TABLE workflow_instances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id INTEGER NOT NULL,
  workflow_id TEXT NOT NULL UNIQUE,
  project TEXT NOT NULL,
  description TEXT,
  status TEXT CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')) DEFAULT 'pending',
  current_phase_id INTEGER,
  params TEXT,                 -- JSON: 実行時パラメータ
  started_at TEXT,
  completed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  error_message TEXT,
  FOREIGN KEY (template_id) REFERENCES workflow_templates(id),
  CONSTRAINT valid_project_name CHECK (project ~ '^[a-z0-9-]+$')
);

-- インデックス
CREATE UNIQUE INDEX idx_workflow_instances_workflow_id ON workflow_instances(workflow_id);
CREATE INDEX idx_workflow_instances_template_id ON workflow_instances(template_id);
CREATE INDEX idx_workflow_instances_project ON workflow_instances(project);
CREATE INDEX idx_workflow_instances_status ON workflow_instances(status);
```

**params JSON 構造:**
```json
{
  "symbol": "AAPL",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "priority": 1,
  "owner": "engineer_001",
  "custom_field": "value"
}
```

---

### テーブル 3: workflow_phases

**用途**: ワークフロー実行フェーズの状態管理

```sql
CREATE TABLE workflow_phases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_instance_id INTEGER NOT NULL,
  phase_id INTEGER NOT NULL,
  sequence INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT CHECK(status IN ('waiting', 'running', 'completed', 'blocked', 'failed')) DEFAULT 'waiting',
  started_at TEXT,
  completed_at TEXT,
  timeout_at TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (workflow_instance_id) REFERENCES workflow_instances(id) ON DELETE CASCADE,
  UNIQUE(workflow_instance_id, phase_id)
);

-- インデックス
CREATE INDEX idx_workflow_phases_workflow_id ON workflow_phases(workflow_instance_id);
CREATE INDEX idx_workflow_phases_status ON workflow_phases(status);
CREATE INDEX idx_workflow_phases_sequence ON workflow_phases(workflow_instance_id, sequence);
```

---

### テーブル 4: dev_tasks（既存テーブル 拡張）

**用途**: 単位タスク・DAG依存関係（既存機能 + BDD統合）

```sql
-- 既存テーブル構造を保持し、以下のカラムを追加
ALTER TABLE dev_tasks ADD COLUMN workflow_instance_id INTEGER REFERENCES workflow_instances(id);
ALTER TABLE dev_tasks ADD COLUMN workflow_phase_id INTEGER REFERENCES workflow_phases(id);
ALTER TABLE dev_tasks ADD COLUMN scenario_id TEXT;         -- Gherkin Scenario ID
ALTER TABLE dev_tasks ADD COLUMN role_required TEXT;       -- orchestrator|EM|Engineer|QA
ALTER TABLE dev_tasks ADD COLUMN pane_id TEXT;             -- tmux pane ID (配置情報)
ALTER TABLE dev_tasks ADD COLUMN created_by TEXT;          -- エージェント ID

-- インデックス追加
CREATE INDEX idx_dev_tasks_workflow_instance ON dev_tasks(workflow_instance_id);
CREATE INDEX idx_dev_tasks_workflow_phase ON dev_tasks(workflow_phase_id);
CREATE INDEX idx_dev_tasks_scenario ON dev_tasks(scenario_id);
CREATE INDEX idx_dev_tasks_role ON dev_tasks(role_required);
```

**拡張フィールドの仕様:**

| フィールド | 型 | 説明 | 例 |
|-----------|-----|------|-----|
| `workflow_instance_id` | INTEGER FK | 所属ワークフロー | 5 |
| `workflow_phase_id` | INTEGER FK | 所属フェーズ | 2 |
| `scenario_id` | TEXT | Gherkin Scenario ID | "scenario:04" |
| `role_required` | TEXT | 実行に必要なロール | "Engineer" / "QA" |
| `pane_id` | TEXT | tmux セッション・ペイン | "exp-stock_orchestrator_wf003_task-3@main:members.0" |
| `created_by` | TEXT | タスク作成エージェント | "orchestrator" |

---

### テーブル 5: task_dependencies（既存テーブル - 既存構造を活用）

**用途**: タスク間 DAG 依存関係（変更なし）

```sql
-- 既存構造：
-- CREATE TABLE task_dependencies (
--   id INTEGER PRIMARY KEY,
--   task_id INTEGER,
--   depends_on_id INTEGER,
--   FOREIGN KEY (task_id) REFERENCES dev_tasks(id),
--   FOREIGN KEY (depends_on_id) REFERENCES dev_tasks(id),
--   UNIQUE(task_id, depends_on_id)
-- );
```

---

### テーブル 6: agent_assignments（新規）

**用途**: エージェント ↔ タスク / ロール割り当て

```sql
CREATE TABLE agent_assignments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL,
  agent_type TEXT CHECK(agent_type IN ('orchestrator', 'em', 'engineer', 'qa')),
  task_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  permission_level INTEGER DEFAULT 1,
  assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT,
  status TEXT CHECK(status IN ('pending', 'active', 'completed', 'failed')) DEFAULT 'pending',
  FOREIGN KEY (task_id) REFERENCES dev_tasks(id) ON DELETE CASCADE,
  UNIQUE(agent_id, task_id)
);

-- インデックス
CREATE INDEX idx_agent_assignments_agent_id ON agent_assignments(agent_id);
CREATE INDEX idx_agent_assignments_task_id ON agent_assignments(task_id);
CREATE INDEX idx_agent_assignments_status ON agent_assignments(status);
```

---

## KuzuDB グラフスキーマ

### ノード定義

```cypher
-- ワークフロー関連
CREATE NODE TABLE Workflow(
  id INT64,
  workflow_id STRING PRIMARY KEY,
  project STRING,
  status STRING
);

CREATE NODE TABLE Phase(
  id INT64,
  phase_id INT64,
  name STRING,
  workflow_id STRING PRIMARY KEY,
  status STRING
);

CREATE NODE TABLE Task(
  id INT64,
  task_id INT64,
  title STRING,
  phase_id INT64 PRIMARY KEY,
  status STRING
);

-- ロール・組織関連
CREATE NODE TABLE Role(
  role_name STRING PRIMARY KEY,
  permission_level INT64
);

CREATE NODE TABLE Agent(
  agent_id STRING PRIMARY KEY,
  agent_type STRING,
  name STRING
);

-- BDD関連
CREATE NODE TABLE Scenario(
  scenario_id STRING PRIMARY KEY,
  feature_name STRING,
  title STRING
);
```

### エッジ定義

```cypher
-- ワークフローフロー
CREATE REL TABLE NEXT_PHASE(
  FROM Workflow TO Phase,
  sequence INT64,
  transition_at STRING
);

CREATE REL TABLE CONTAINS_TASK(
  FROM Phase TO Task,
  sequence INT64
);

-- タスク依存関係
CREATE REL TABLE DEPENDS_ON(
  FROM Task TO Task,
  type STRING,
  priority INT64
);

-- 割り当て関係
CREATE REL TABLE ASSIGNED_TO(
  FROM Agent TO Task,
  role STRING,
  permission_level INT64,
  assigned_at STRING
);

CREATE REL TABLE HAS_ROLE(
  FROM Agent TO Role,
  permission_level INT64
);

-- BDD マッピング
CREATE REL TABLE IMPLEMENTS(
  FROM Task TO Scenario,
  mapping_status STRING,
  coverage_percent INT64
);

CREATE REL TABLE DEFINED_IN(
  FROM Scenario TO Workflow,
  template_id INT64
);
```

---

## テーブル間の関連性

### リレーションシップ図（ER図相当）

```
workflow_templates
  ├─ id (PK)
  └─ name (UNIQUE)
       ↓ (1:N)
workflow_instances
  ├─ id (PK)
  ├─ template_id (FK)
  └─ workflow_id (UNIQUE)
       ↓ (1:N)
workflow_phases
  ├─ id (PK)
  ├─ workflow_instance_id (FK)
  └─ sequence
       ↓ (1:N)
dev_tasks
  ├─ id (PK)
  ├─ workflow_instance_id (FK)
  ├─ workflow_phase_id (FK)
  ├─ status
  └─ blockedBy, blocks (DAG)
       ↓ (1:N)
task_dependencies
  ├─ task_id (FK)
  └─ depends_on_id (FK)

agent_assignments
  ├─ agent_id
  ├─ task_id (FK → dev_tasks)
  └─ role
```

### 列挙体（Enum）定義

**Workflow Status:**
```
pending → running → completed
         ├→ failed
         └→ cancelled
```

**Phase Status:**
```
waiting → running → completed
        ├→ blocked (依存タスク未完了)
        └→ failed
```

**Task Status:**
```
pending → in_progress → reviewing → completed
  ↓          ↓                         ↑
blocked ←─────────────────────────────┘

needs_fix → pending (テスト失敗時の再実装)
```

---

## ステータス遷移と制約

### Phase 遷移ロジック

```
Phase N (waiting)
  ├─ check: 前フェーズ N-1 が completed か？
  │   ├─ Yes → Phase N: running
  │   └─ No  → Phase N: blocked
  │
Phase N (running)
  ├─ check: 全 Task が completed か？
  │   ├─ Yes → Phase N: completed
  │   │        └─ trigger: Phase N+1 を waiting → running へ遷移
  │   └─ No  → timeout_at に達したか？
  │            ├─ Yes → Phase N: failed
  │            └─ No  → 待機継続
  │
Phase N (failed)
  └─ rollback: 依存タスク再実装のため、Task status を pending に戻す
```

### タスク DAG 検証ルール

1. **循環参照チェック**: Task A → B → C → A のようなループを禁止
2. **依存タスク完了確認**: Task status が pending のまま in_progress 遷移不可（blockedBy が空の場合のみ可能）
3. **フェーズ境界制約**: Phase N のタスク依存は Phase N + Phase N+1 内のみ（遡行依存は禁止）

---

## 整合性確認

### task-manager-sqlite との統合

#### マッピング表

| BDD 概念 | task-manager-sqlite | 統合方法 | 後方互換性 |
|---------|-----------------|---------|----------|
| **Workflow Template** | `workflow_templates` (新規) | feature_file 参照 | N/A |
| **Workflow Instance** | `workflow_instances` (新規) | template_id 紐付け | ✓ 既存タスクは NULL |
| **Phase** | `workflow_phases` (新規) | タスクをフェーズ分類 | ✓ 既存タスクは phase_id = NULL |
| **Task** | `dev_tasks` (拡張) | workflow_instance_id 追加 | ✓ 既存コマンド不変 |
| **DAG** | `task_dependencies` (既存) | 変更なし | ✓ 完全互換 |
| **Assignment** | `agent_assignments` (新規) | ロール管理分離 | ✓ assigned_to は継続 |

#### API 互換性

**既存コマンド（変更なし）:**
```bash
task.py list [--status S] [--project P]
task.py add "title" --priority N
task.py update <ID> --status S
task.py done <ID>
task.py dep add <A> <B>
```

**新規コマンド（BDD統合）:**
```bash
task.py wf template list
task.py wf instance start <TEMPLATE_ID> "name" --params '{"key":"value"}'
task.py wf instance status <INSTANCE_ID>
task.py wf phase advance <INSTANCE_ID> <PHASE_ID>
```

---

## 実装チェックリスト

- [ ] workflow_templates テーブル作成
- [ ] workflow_instances テーブル作成
- [ ] workflow_phases テーブル作成
- [ ] dev_tasks テーブル拡張（5カラム追加）
- [ ] agent_assignments テーブル作成
- [ ] KuzuDB ノード定義
- [ ] KuzuDB エッジ定義
- [ ] インデックス作成（パフォーマンス最適化）
- [ ] 既存コマンド後方互換性テスト
- [ ] migration スクリプト作成

