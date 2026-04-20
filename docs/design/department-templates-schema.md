# 部署テンプレートライブラリ - スキーマ・業務フロー設計

**作成日**: 2026-04-20  
**バージョン**: v1.0  
**ステータス**: 設計フェーズ完了  
**対応**: タスク #2369

---

## 目次

1. [概要](#1-概要)
2. [SQLiteスキーマ設計](#2-sqliteスキーマ設計)
3. [KuzuDBグラフ構造](#3-kuzudbグラフ構造)
4. [部署別テンプレート定義](#4-部署別テンプレート定義)
5. [実装ガイドライン](#5-実装ガイドライン)

---

## 1. 概要

### 1-1. 部署テンプレートの位置づけ

部署テンプレート（Department Templates）は、ワークフローテンプレートシステムの上に構築される**ドメイン固有テンプレート**です。

```
ワークフローテンプレートシステム（汎用）
  ├─ workflow_templates
  ├─ wf_template_phases
  ├─ wf_template_tasks
  └─ (フェーズ・タスク駆動)
       ↓
部署テンプレート（組織固有）
  ├─ departments_templates
  ├─ department_template_roles
  ├─ department_template_processes
  └─ department_template_tasks
       ↓
部署インスタンス（実行）
  ├─ department_instances
  ├─ department_instance_members
  └─ department_instance_workflows
```

### 1-2. 部署テンプレート実装の原則

| 原則 | 説明 |
|-----|------|
| **再利用性** | 同一部署テンプレートから複数の部署インスタンスを生成可能 |
| **構成可能性** | テンプレートの組み合わせで複合部署（複数テンプレート適用）をサポート |
| **トレーサビリティ** | 部署インスタンス→テンプレート→ワークフローの追跡可能性を確保 |
| **スケーラビリティ** | 部署数・メンバー数の増加に対応（SQLiteのインデックス戦略） |

---

## 2. SQLiteスキーマ設計

### 2-1. テーブル設計の全体図

```
┌────────────────────────────────────────────────────────────────┐
│             部署テンプレート層（Template）                      │
│                                                                │
│  ┌──────────────────────────┐                                │
│  │  departments_templates   │                                │
│  │                          │                                │
│  │ id (PK)                  │                                │
│  │ name (部署名)            │                                │
│  │ description              │                                │
│  │ category (back-office/tech/ops)                           │
│  │ version                  │                                │
│  │ status                   │                                │
│  └─────────┬────────────────┘                                │
│            │ 1:N                                              │
│            ├─────────────────────────────────┐               │
│            │                                 │               │
│     ┌──────▼──────────────────────┐   ┌─────▼─────────────┐ │
│     │ department_template_roles   │   │department_template│ │
│     │                             │   │   _processes      │ │
│     │ id (PK)                     │   │                   │ │
│     │ template_id (FK)            │   │ id (PK)           │ │
│     │ role_key (finance/legal/hr) │   │ template_id (FK)  │ │
│     │ role_label                  │   │ process_key       │ │
│     │ responsibility              │   │ process_label     │ │
│     │ required_skills             │   │ process_order     │ │
│     │ min_members                 │   │ description       │ │
│     │ max_members                 │   │ responsible_role  │ │
│     │ config (JSON)               │   │ estimated_hours   │ │
│     └──────────────────────────────┘   │ config (JSON)     │ │
│                                        └─────┬─────────────┘ │
│                                              │ 1:N            │
│                                        ┌─────▼────────────────┐
│                                        │department_template   │
│                                        │  _tasks              │
│                                        │                      │
│                                        │ id (PK)              │
│                                        │ process_id (FK)      │
│                                        │ task_key             │
│                                        │ task_title           │
│                                        │ task_description     │
│                                        │ category             │
│                                        │ assigned_role_key    │
│                                        │ estimated_hours      │
│                                        │ depends_on_key       │
│                                        │ priority             │
│                                        │ config (JSON)        │
│                                        └──────────────────────┘
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│             部署インスタンス層（Instance）                      │
│                                                                │
│  ┌──────────────────────────┐                                │
│  │  department_instances    │                                │
│  │                          │                                │
│  │ id (PK)                  │                                │
│  │ template_id (FK)         │                                │
│  │ name (部署名)            │                                │
│  │ status                   │                                │
│  │ organization_id          │                                │
│  │ location                 │                                │
│  │ config (JSON)            │                                │
│  └─────────┬────────────────┘                                │
│            │ 1:N                                              │
│            │                                                  │
│     ┌──────▼────────────────────────┐                       │
│     │ department_instance_members    │                       │
│     │                                │                       │
│     │ id (PK)                        │                       │
│     │ instance_id (FK)               │                       │
│     │ agent_id (FK → agents)         │                       │
│     │ role_key                       │                       │
│     │ status (active/inactive)       │                       │
│     │ assigned_at                    │                       │
│     │ UNIQUE(instance_id, agent_id)  │                       │
│     └─────────────────────────────────┘                       │
│                                                                │
│     ┌──────────────────────────────────────────────────────┐  │
│     │ department_instance_workflows                        │  │
│     │                                                      │  │
│     │ id (PK)                                             │  │
│     │ instance_id (FK)                                    │  │
│     │ process_id (FK → department_template_processes)     │  │
│     │ workflow_instance_id (FK → workflow_instances)      │  │
│     │ status (pending/running/completed/failed)           │  │
│     │ started_at / completed_at                           │  │
│     └──────────────────────────────────────────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 2-2. テーブル詳細仕様

#### 1. `departments_templates` - 部署テンプレート定義

```sql
CREATE TABLE IF NOT EXISTS departments_templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,        -- 例: "Finance Department", "Legal Department"
    description     TEXT,                        -- 部署の説明
    category        TEXT NOT NULL,               -- 'back-office', 'tech', 'ops', 'support'
    version         INTEGER DEFAULT 1,           -- テンプレートバージョン
    status          TEXT DEFAULT 'draft',        -- draft / active / deprecated
    total_roles     INTEGER DEFAULT 0,           -- ロール数（キャッシュ）
    total_processes INTEGER DEFAULT 0,           -- プロセス数（キャッシュ）
    total_tasks     INTEGER DEFAULT 0,           -- タスク数（キャッシュ）
    config          TEXT,                        -- JSON（部署固有設定）
    created_by      TEXT,                        -- 作成者
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_departments_templates_status 
  ON departments_templates(status);
CREATE INDEX IF NOT EXISTS idx_departments_templates_category 
  ON departments_templates(category);
```

**config フィールドの例**:
```json
{
  "min_total_members": 3,
  "max_total_members": 20,
  "budget_allocation": {"salary": 0.7, "tools": 0.2, "training": 0.1},
  "required_certifications": ["ISO-9001", "SOX-compliance"],
  "kpi_targets": {"process_efficiency": 0.85, "error_rate": 0.01}
}
```

---

#### 2. `department_template_roles` - 部署内の役割定義

```sql
CREATE TABLE IF NOT EXISTS department_template_roles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL REFERENCES departments_templates(id),
    role_key         TEXT NOT NULL,              -- 例: 'finance-manager', 'accountant', 'auditor'
    role_label       TEXT NOT NULL,              -- 表示名（例: "財務マネージャー"）
    role_order       INTEGER NOT NULL,           -- 階層順（1=最上位）
    responsibility   TEXT,                       -- 職責説明
    required_skills  TEXT,                       -- JSON配列（["accounting", "tax", "audit"]）
    min_members      INTEGER DEFAULT 1,          -- このロールに必要な最小メンバー数
    max_members      INTEGER,                    -- 最大メンバー数（NULL=無制限）
    supervisor_role_key TEXT,                    -- 上司ロール（例: 'finance-manager' が 'accountant' の上司）
    config           TEXT,                       -- JSON（ロール固有設定）
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, role_key),
    UNIQUE(template_id, role_order)
);

CREATE INDEX IF NOT EXISTS idx_department_template_roles_template_id 
  ON department_template_roles(template_id);
```

**required_skills の例**:
```json
["accounting", "tax_planning", "financial_analysis", "compliance"]
```

**supervisor_role_key の例**:
- accountant → finance-manager
- intern → accountant

---

#### 3. `department_template_processes` - 業務プロセス定義

```sql
CREATE TABLE IF NOT EXISTS department_template_processes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL REFERENCES departments_templates(id),
    process_key      TEXT NOT NULL,              -- 例: 'monthly-closing', 'tax-filing', 'audit-prep'
    process_label    TEXT NOT NULL,              -- 表示名
    process_order    INTEGER NOT NULL,           -- 実行順序
    description      TEXT,                       -- プロセス説明
    responsible_role_key TEXT NOT NULL,          -- 担当ロール（FK）
    estimated_hours  INTEGER,                    -- 見積もり工数
    frequency        TEXT,                       -- 'daily', 'weekly', 'monthly', 'quarterly', 'annual', 'ad-hoc'
    doc_requirements TEXT,                       -- JSON配列（成果物要件）
    config           TEXT,                       -- JSON（プロセス固有設定）
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, process_key),
    UNIQUE(template_id, process_order)
);

CREATE INDEX IF NOT EXISTS idx_department_template_processes_template_id 
  ON department_template_processes(template_id);
```

**frequency の設定値**:
- `daily`: 毎日（例: "日報入力"）
- `weekly`: 毎週（例: "週次レビュー"）
- `monthly`: 毎月（例: "月次決算"）
- `quarterly`: 四半期（例: "四半期決算"）
- `annual`: 年1回（例: "決算監査"）
- `ad-hoc`: 不定期（例: "特別会議"）

**doc_requirements の例**:
```json
[
  {"name": "Closing Report", "format": "xlsx", "mandatory": true},
  {"name": "Variance Analysis", "format": "pdf", "mandatory": true},
  {"name": "Management Summary", "format": "docx", "mandatory": false}
]
```

---

#### 4. `department_template_tasks` - プロセス内のタスク定義

```sql
CREATE TABLE IF NOT EXISTS department_template_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id        INTEGER NOT NULL REFERENCES department_template_processes(id),
    template_id       INTEGER NOT NULL REFERENCES departments_templates(id),
    task_key          TEXT NOT NULL,             -- 例: 'reconcile-ledger', 'prepare-report'
    task_title        TEXT NOT NULL,             -- タスク名
    task_description  TEXT,                      -- タスク説明（プレースホルダ対応）
    assigned_role_key TEXT NOT NULL,             -- 担当ロール（FK）
    category          TEXT,                      -- 'data-entry', 'validation', 'analysis', 'review', 'approval'
    estimated_hours   REAL,                      -- 見積もり工数
    depends_on_key    TEXT,                      -- 依存タスク（同一プロセス内）
    priority          INTEGER DEFAULT 3,         -- 優先度（1=高, 2=中, 3=低）
    success_criteria  TEXT,                      -- JSON（成功基準）
    config            TEXT,                      -- JSON（タスク固有設定）
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(process_id, task_key)
);

CREATE INDEX IF NOT EXISTS idx_department_template_tasks_process_id 
  ON department_template_tasks(process_id);
```

**success_criteria の例**:
```json
{
  "accuracy_threshold": 0.99,
  "required_approvals": 1,
  "time_limit_minutes": 120,
  "output_validation": {
    "total_rows": {">": 0},
    "balance_check": {"must_equal": "previous_month"}
  }
}
```

---

### 2-3. インスタンス層テーブル

#### 5. `department_instances` - 部署インスタンス

```sql
CREATE TABLE IF NOT EXISTS department_instances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id     INTEGER NOT NULL REFERENCES departments_templates(id),
    name            TEXT NOT NULL,               -- 例: "Tokyo Finance Department"
    status          TEXT DEFAULT 'active',       -- 'planning' / 'active' / 'suspended' / 'closed'
    organization_id TEXT,                        -- 所属組織ID（外部システム連携）
    location        TEXT,                        -- 拠点（例: "Tokyo", "Singapore"）
    manager_agent_id INTEGER REFERENCES agents(id), -- 部長/管理者エージェント
    context         TEXT,                        -- JSON（部署固有変数）
    member_count    INTEGER DEFAULT 0,           -- メンバー数（キャッシュ）
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    started_at      TEXT,                        -- 運用開始日
    closed_at       TEXT                         -- 終了日（status='closed'の場合）
);

CREATE INDEX IF NOT EXISTS idx_department_instances_template_id 
  ON department_instances(template_id);
CREATE INDEX IF NOT EXISTS idx_department_instances_status 
  ON department_instances(status);
```

**context フィールドの例**:
```json
{
  "budget_allocated": 500000,
  "fiscal_year": 2026,
  "reporting_currency": "JPY",
  "compliance_framework": "IFRS",
  "custom_fields": {
    "department_code": "FIN-01",
    "cost_center": "CC-1001"
  }
}
```

---

#### 6. `department_instance_members` - 部署メンバー割り当て

```sql
CREATE TABLE IF NOT EXISTS department_instance_members (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id      INTEGER NOT NULL REFERENCES department_instances(id),
    agent_id         INTEGER NOT NULL REFERENCES agents(id),
    role_key         TEXT NOT NULL,              -- 割り当てたロール
    status           TEXT DEFAULT 'active',      -- 'active' / 'inactive' / 'on-leave'
    start_date       TEXT NOT NULL DEFAULT (date('now')),
    end_date         TEXT,                       -- 任期終了日
    assigned_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_department_instance_members_instance_id 
  ON department_instance_members(instance_id);
CREATE INDEX IF NOT EXISTS idx_department_instance_members_agent_id 
  ON department_instance_members(agent_id);
```

---

#### 7. `department_instance_workflows` - プロセス実行ワークフロー

```sql
CREATE TABLE IF NOT EXISTS department_instance_workflows (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id           INTEGER NOT NULL REFERENCES department_instances(id),
    process_id            INTEGER NOT NULL REFERENCES department_template_processes(id),
    workflow_instance_id  INTEGER REFERENCES workflow_instances(id),
    execution_count       INTEGER DEFAULT 1,     -- この月の実行回数
    status                TEXT DEFAULT 'pending', -- 'pending' / 'running' / 'completed' / 'failed' / 'paused'
    scheduled_date        TEXT,                  -- 予定実行日
    started_at            TEXT,                  -- 実際開始日時
    completed_at          TEXT,                  -- 実際完了日時
    result_notes          TEXT,                  -- 実行結果のメモ
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, process_id, execution_count)
);

CREATE INDEX IF NOT EXISTS idx_department_instance_workflows_instance_id 
  ON department_instance_workflows(instance_id);
CREATE INDEX IF NOT EXISTS idx_department_instance_workflows_status 
  ON department_instance_workflows(status);
```

---

## 3. KuzuDBグラフ構造

### 3-1. グラフノード定義

部署テンプレートのノード（vertex）定義：

```
DepartmentTemplate
  ├─ id: INTEGER
  ├─ name: STRING
  ├─ category: STRING
  └─ version: INTEGER

Role
  ├─ role_key: STRING
  ├─ role_label: STRING
  ├─ hierarchy_level: INTEGER
  └─ required_skills: LIST[STRING]

Process
  ├─ process_key: STRING
  ├─ process_label: STRING
  ├─ frequency: STRING
  └─ estimated_hours: INTEGER

Task
  ├─ task_key: STRING
  ├─ task_title: STRING
  ├─ estimated_hours: FLOAT
  └─ category: STRING

Skill
  ├─ skill_name: STRING
  ├─ skill_level: STRING (beginner/intermediate/expert)
  └─ certification: STRING
```

### 3-2. グラフエッジ定義

```
DepartmentTemplate --[has_role]-->      Role
                                        │
                                        ├─ [supervises]    ──> Role
                                        │
                                        └─ [leads_process]──> Process

Role --[executes]-->   Process
                        │
                        └─ [contains_task] ──> Task
                                                 │
                                                 ├─ [requires_skill] ──> Skill
                                                 │
                                                 └─ [depends_on] ──> Task

DepartmentTemplate --[defines]-->  Process
                                    │
                                    └─ [includes_task] ──> Task
```

### 3-3. KuzuDBクエリ例

#### 例1: 部署テンプレートのロール階層構造

```cypher
MATCH (dt:DepartmentTemplate {name: "Finance Department"})
      -[has_role]->(r:Role)
      -[supervises*0..]->(sub_r:Role)
RETURN dt.name, r.role_label, sub_r.role_label, LENGTH(supervises) AS hierarchy_depth
ORDER BY hierarchy_depth, r.role_order
```

#### 例2: 特定ロールが実行すべきプロセスとタスク

```cypher
MATCH (role:Role {role_key: "accountant"})
      -[leads_process|executes]->(proc:Process)
      -[contains_task]->(task:Task)
RETURN proc.process_label, task.task_title, task.estimated_hours
ORDER BY proc.process_order, task.task_key
```

#### 例3: 必要スキルの確認

```cypher
MATCH (task:Task {task_key: "reconcile-ledger"})
      <-[requires_skill]-(skill:Skill)
RETURN task.task_title, skill.skill_name, skill.skill_level
```

---

## 4. 部署別テンプレート定義

### 4-1. 経理部（Finance Department）

#### テンプレート基本情報

```json
{
  "name": "Finance Department",
  "category": "back-office",
  "description": "財務管理・経理業務を担当する部署",
  "roles": [
    {
      "role_key": "finance-director",
      "role_label": "財務部長",
      "role_order": 1,
      "min_members": 1,
      "max_members": 1,
      "responsibility": "財務戦略の企画・実行、部署全体の統括"
    },
    {
      "role_key": "finance-manager",
      "role_label": "財務マネージャー",
      "role_order": 2,
      "supervisor_role_key": "finance-director",
      "min_members": 1,
      "max_members": 3,
      "required_skills": ["accounting", "tax_planning", "financial_analysis"]
    },
    {
      "role_key": "accountant",
      "role_label": "経理",
      "role_order": 3,
      "supervisor_role_key": "finance-manager",
      "min_members": 2,
      "max_members": 5,
      "required_skills": ["journal_entry", "reconciliation", "compliance"]
    },
    {
      "role_key": "audit-specialist",
      "role_label": "監査担当",
      "role_order": 2,
      "supervisor_role_key": "finance-director",
      "min_members": 1,
      "required_skills": ["audit", "risk_assessment", "compliance_review"]
    }
  ],
  "processes": [
    {
      "process_key": "daily-cash-management",
      "process_label": "日次現金管理",
      "process_order": 1,
      "responsible_role_key": "accountant",
      "frequency": "daily",
      "estimated_hours": 1,
      "tasks": [
        {
          "task_key": "reconcile-cash-accounts",
          "task_title": "現金勘定の照合",
          "assigned_role_key": "accountant",
          "category": "validation",
          "estimated_hours": 0.5,
          "priority": 1
        },
        {
          "task_key": "record-daily-transactions",
          "task_title": "日次取引記録",
          "assigned_role_key": "accountant",
          "category": "data-entry",
          "estimated_hours": 0.5,
          "depends_on_key": "reconcile-cash-accounts",
          "priority": 1
        }
      ]
    },
    {
      "process_key": "monthly-closing",
      "process_label": "月次決算",
      "process_order": 2,
      "responsible_role_key": "finance-manager",
      "frequency": "monthly",
      "estimated_hours": 16,
      "doc_requirements": [
        {"name": "Trial Balance", "format": "xlsx", "mandatory": true},
        {"name": "General Ledger", "format": "xlsx", "mandatory": true},
        {"name": "Monthly Report", "format": "pdf", "mandatory": true}
      ],
      "tasks": [
        {
          "task_key": "reconcile-ledger",
          "task_title": "元帳照合",
          "assigned_role_key": "accountant",
          "category": "validation",
          "estimated_hours": 2,
          "priority": 1
        },
        {
          "task_key": "prepare-trial-balance",
          "task_title": "試算表作成",
          "assigned_role_key": "accountant",
          "category": "analysis",
          "estimated_hours": 2,
          "depends_on_key": "reconcile-ledger",
          "priority": 1
        },
        {
          "task_key": "review-adjustments",
          "task_title": "決算整理項目の検討",
          "assigned_role_key": "finance-manager",
          "category": "review",
          "estimated_hours": 3,
          "depends_on_key": "prepare-trial-balance",
          "priority": 1
        },
        {
          "task_key": "approve-closing",
          "task_title": "月次決算の承認",
          "assigned_role_key": "finance-director",
          "category": "approval",
          "estimated_hours": 1,
          "depends_on_key": "review-adjustments",
          "priority": 1
        }
      ]
    },
    {
      "process_key": "quarterly-audit",
      "process_label": "四半期監査",
      "process_order": 3,
      "responsible_role_key": "audit-specialist",
      "frequency": "quarterly",
      "estimated_hours": 24,
      "tasks": [
        {
          "task_key": "audit-planning",
          "task_title": "監査計画作成",
          "assigned_role_key": "audit-specialist",
          "category": "analysis",
          "estimated_hours": 4,
          "priority": 1
        },
        {
          "task_key": "conduct-audit",
          "task_title": "監査実施",
          "assigned_role_key": "audit-specialist",
          "category": "validation",
          "estimated_hours": 12,
          "depends_on_key": "audit-planning",
          "priority": 1
        },
        {
          "task_key": "audit-report",
          "task_title": "監査報告書作成",
          "assigned_role_key": "audit-specialist",
          "category": "analysis",
          "estimated_hours": 8,
          "depends_on_key": "conduct-audit",
          "priority": 1
        }
      ]
    }
  ]
}
```

### 4-2. 法務部（Legal Department）

```json
{
  "name": "Legal Department",
  "category": "back-office",
  "description": "法務・コンプライアンス業務を担当する部署",
  "roles": [
    {
      "role_key": "general-counsel",
      "role_label": "法務部長",
      "role_order": 1,
      "min_members": 1,
      "max_members": 1,
      "required_skills": ["legal_strategy", "contract_negotiation", "compliance"]
    },
    {
      "role_key": "legal-manager",
      "role_label": "法務マネージャー",
      "role_order": 2,
      "supervisor_role_key": "general-counsel",
      "min_members": 1,
      "max_members": 2,
      "required_skills": ["contract_review", "legal_analysis", "risk_management"]
    },
    {
      "role_key": "compliance-officer",
      "role_label": "コンプライアンス担当",
      "role_order": 2,
      "supervisor_role_key": "general-counsel",
      "min_members": 1,
      "max_members": 2,
      "required_skills": ["regulatory_compliance", "audit", "policy_development"]
    },
    {
      "role_key": "legal-specialist",
      "role_label": "法務スペシャリスト",
      "role_order": 3,
      "supervisor_role_key": "legal-manager",
      "min_members": 1,
      "max_members": 3,
      "required_skills": ["contract_drafting", "legal_research", "documentation"]
    }
  ],
  "processes": [
    {
      "process_key": "contract-management",
      "process_label": "契約管理",
      "process_order": 1,
      "responsible_role_key": "legal-manager",
      "frequency": "ad-hoc",
      "estimated_hours": 8,
      "tasks": [
        {
          "task_key": "contract-intake",
          "task_title": "契約書受付・分類",
          "assigned_role_key": "legal-specialist",
          "category": "data-entry",
          "estimated_hours": 1
        },
        {
          "task_key": "contract-review",
          "task_title": "契約書レビュー",
          "assigned_role_key": "legal-manager",
          "category": "review",
          "estimated_hours": 4,
          "depends_on_key": "contract-intake"
        },
        {
          "task_key": "contract-approval",
          "task_title": "契約承認",
          "assigned_role_key": "general-counsel",
          "category": "approval",
          "estimated_hours": 2,
          "depends_on_key": "contract-review"
        }
      ]
    },
    {
      "process_key": "compliance-audit",
      "process_label": "コンプライアンス監査",
      "process_order": 2,
      "responsible_role_key": "compliance-officer",
      "frequency": "quarterly",
      "estimated_hours": 20,
      "tasks": [
        {
          "task_key": "compliance-check",
          "task_title": "コンプライアンス確認",
          "assigned_role_key": "compliance-officer",
          "category": "validation",
          "estimated_hours": 8
        },
        {
          "task_key": "remediation-plan",
          "task_title": "改善計画作成",
          "assigned_role_key": "compliance-officer",
          "category": "analysis",
          "estimated_hours": 6,
          "depends_on_key": "compliance-check"
        },
        {
          "task_key": "executive-report",
          "task_title": "経営層報告",
          "assigned_role_key": "general-counsel",
          "category": "approval",
          "estimated_hours": 2,
          "depends_on_key": "remediation-plan"
        }
      ]
    }
  ]
}
```

### 4-3. 人事部（HR Department）

```json
{
  "name": "HR Department",
  "category": "back-office",
  "description": "人材採用・育成・管理を担当する部署",
  "roles": [
    {
      "role_key": "hr-director",
      "role_label": "人事部長",
      "role_order": 1,
      "min_members": 1,
      "max_members": 1,
      "required_skills": ["talent_management", "organizational_development", "strategic_planning"]
    },
    {
      "role_key": "hr-manager",
      "role_label": "人事マネージャー",
      "role_order": 2,
      "supervisor_role_key": "hr-director",
      "min_members": 1,
      "max_members": 2,
      "required_skills": ["recruitment", "employee_relations", "performance_management"]
    },
    {
      "role_key": "hr-specialist",
      "role_label": "人事スペシャリスト",
      "role_order": 3,
      "supervisor_role_key": "hr-manager",
      "min_members": 1,
      "max_members": 3,
      "required_skills": ["payroll", "benefits_administration", "record_keeping"]
    }
  ],
  "processes": [
    {
      "process_key": "recruitment",
      "process_label": "採用プロセス",
      "process_order": 1,
      "responsible_role_key": "hr-manager",
      "frequency": "ad-hoc",
      "estimated_hours": 40,
      "tasks": [
        {
          "task_key": "job-posting",
          "task_title": "求人票作成・掲載",
          "assigned_role_key": "hr-manager",
          "category": "data-entry",
          "estimated_hours": 2
        },
        {
          "task_key": "candidate-screening",
          "task_title": "応募者選別",
          "assigned_role_key": "hr-specialist",
          "category": "validation",
          "estimated_hours": 8,
          "depends_on_key": "job-posting"
        },
        {
          "task_key": "interview-coordination",
          "task_title": "面接調整",
          "assigned_role_key": "hr-specialist",
          "category": "data-entry",
          "estimated_hours": 4,
          "depends_on_key": "candidate-screening"
        },
        {
          "task_key": "offer-decision",
          "task_title": "内定決定",
          "assigned_role_key": "hr-manager",
          "category": "approval",
          "estimated_hours": 2,
          "depends_on_key": "interview-coordination"
        }
      ]
    },
    {
      "process_key": "performance-review",
      "process_label": "人事評価",
      "process_order": 2,
      "responsible_role_key": "hr-manager",
      "frequency": "annual",
      "estimated_hours": 30,
      "tasks": [
        {
          "task_key": "review-planning",
          "task_title": "評価スケジュール企画",
          "assigned_role_key": "hr-manager",
          "category": "analysis",
          "estimated_hours": 4
        },
        {
          "task_key": "self-assessment-collection",
          "task_title": "自己評価回収",
          "assigned_role_key": "hr-specialist",
          "category": "data-entry",
          "estimated_hours": 4,
          "depends_on_key": "review-planning"
        },
        {
          "task_key": "manager-feedback",
          "task_title": "管理職フィードバック作成",
          "assigned_role_key": "hr-manager",
          "category": "review",
          "estimated_hours": 10,
          "depends_on_key": "self-assessment-collection"
        },
        {
          "task_key": "review-finalization",
          "task_title": "評価書確定・承認",
          "assigned_role_key": "hr-director",
          "category": "approval",
          "estimated_hours": 2,
          "depends_on_key": "manager-feedback"
        }
      ]
    }
  ]
}
```

### 4-4. 開発部（Development Department）

```json
{
  "name": "Development Department",
  "category": "tech",
  "description": "プロダクト開発・エンジニアリングを担当する部署",
  "roles": [
    {
      "role_key": "tech-lead",
      "role_label": "技術責任者",
      "role_order": 1,
      "min_members": 1,
      "max_members": 1,
      "required_skills": ["system_architecture", "technical_leadership", "code_review"]
    },
    {
      "role_key": "engineering-manager",
      "role_label": "エンジニアリング・マネージャー",
      "role_order": 2,
      "supervisor_role_key": "tech-lead",
      "min_members": 1,
      "max_members": 2,
      "required_skills": ["team_management", "project_planning", "technical_mentoring"]
    },
    {
      "role_key": "senior-engineer",
      "role_label": "シニアエンジニア",
      "role_order": 3,
      "supervisor_role_key": "engineering-manager",
      "min_members": 1,
      "max_members": 3,
      "required_skills": ["full_stack_development", "database_design", "system_optimization"]
    },
    {
      "role_key": "engineer",
      "role_label": "エンジニア",
      "role_order": 4,
      "supervisor_role_key": "engineering-manager",
      "min_members": 2,
      "max_members": 8,
      "required_skills": ["programming", "testing", "version_control"]
    },
    {
      "role_key": "qa-engineer",
      "role_label": "QAエンジニア",
      "role_order": 3,
      "supervisor_role_key": "tech-lead",
      "min_members": 1,
      "max_members": 2,
      "required_skills": ["test_automation", "quality_assurance", "bug_reporting"]
    }
  ],
  "processes": [
    {
      "process_key": "feature-development",
      "process_label": "機能開発",
      "process_order": 1,
      "responsible_role_key": "engineering-manager",
      "frequency": "weekly",
      "estimated_hours": 80,
      "tasks": [
        {
          "task_key": "design-review",
          "task_title": "設計レビュー",
          "assigned_role_key": "senior-engineer",
          "category": "review",
          "estimated_hours": 4
        },
        {
          "task_key": "implementation",
          "task_title": "実装",
          "assigned_role_key": "engineer",
          "category": "implement",
          "estimated_hours": 40,
          "depends_on_key": "design-review"
        },
        {
          "task_key": "code-review",
          "task_title": "コードレビュー",
          "assigned_role_key": "senior-engineer",
          "category": "review",
          "estimated_hours": 8,
          "depends_on_key": "implementation"
        },
        {
          "task_key": "merge-to-main",
          "task_title": "メインブランチへマージ",
          "assigned_role_key": "tech-lead",
          "category": "approval",
          "estimated_hours": 2,
          "depends_on_key": "code-review"
        }
      ]
    },
    {
      "process_key": "testing-release",
      "process_label": "テスト・リリース",
      "process_order": 2,
      "responsible_role_key": "qa-engineer",
      "frequency": "weekly",
      "estimated_hours": 24,
      "tasks": [
        {
          "task_key": "test-planning",
          "task_title": "テスト計画作成",
          "assigned_role_key": "qa-engineer",
          "category": "analysis",
          "estimated_hours": 2
        },
        {
          "task_key": "unit-testing",
          "task_title": "単体テスト実施",
          "assigned_role_key": "engineer",
          "category": "validation",
          "estimated_hours": 8,
          "depends_on_key": "test-planning"
        },
        {
          "task_key": "e2e-testing",
          "task_title": "E2Eテスト実施",
          "assigned_role_key": "qa-engineer",
          "category": "validation",
          "estimated_hours": 8,
          "depends_on_key": "unit-testing"
        },
        {
          "task_key": "release-approval",
          "task_title": "リリース承認",
          "assigned_role_key": "tech-lead",
          "category": "approval",
          "estimated_hours": 2,
          "depends_on_key": "e2e-testing"
        }
      ]
    }
  ]
}
```

---

## 5. 実装ガイドライン

### 5-1. 実装フェーズ

| フェーズ | タスク | 担当 | 期限 |
|---------|--------|------|------|
| **Phase 1: データベース設計** | テーブルスキーマ確定・マイグレーション | Engineer | 2026-04-23 |
| **Phase 2: KuzuDB統合** | グラフ構造実装・クエリ検証 | Engineer | 2026-04-25 |
| **Phase 3: API実装** | テンプレートCRUD・インスタンス化API | Engineer | 2026-04-30 |
| **Phase 4: テスト・ドキュメント** | ユニットテスト・E2Eテスト | QA | 2026-05-05 |

### 5-2. 実装チェックリスト

#### データベース実装
- [ ] `departments_templates` テーブル作成
- [ ] `department_template_roles` テーブル作成
- [ ] `department_template_processes` テーブル作成
- [ ] `department_template_tasks` テーブル作成
- [ ] インスタンス層テーブル作成（5, 6, 7）
- [ ] インデックス最適化
- [ ] マイグレーション検証（冪等性）

#### KuzuDB実装
- [ ] ノード定義の実装
- [ ] エッジ定義の実装
- [ ] 階層構造クエリの検証
- [ ] スキル依存関係の可視化

#### API実装
- [ ] テンプレート一覧取得
- [ ] テンプレート詳細取得
- [ ] テンプレート作成
- [ ] インスタンス化（自動タスク生成）
- [ ] インスタンス照会
- [ ] メンバー割り当て

#### テスト・ドキュメント
- [ ] ユニットテスト（各エンドポイント）
- [ ] 統合テスト（テンプレート→インスタンス→タスク生成フロー）
- [ ] E2Eテスト（UI/APIの組み合わせ）
- [ ] パフォーマンステスト（1000インスタンス以上）
- [ ] APIドキュメント（OpenAPI/Swagger）

### 5-3. データ一貫性・制約

#### テンプレート層の制約

```sql
-- role_key 一意性チェック
CONSTRAINT UNIQUE(template_id, role_key) ON department_template_roles

-- process_order 一意性チェック
CONSTRAINT UNIQUE(template_id, process_order) ON department_template_processes

-- task_key 一意性チェック
CONSTRAINT UNIQUE(process_id, task_key) ON department_template_tasks

-- 外部キー制約
CONSTRAINT FK_responsible_role_key 
  ON department_template_processes(template_id, responsible_role_key)
  REFERENCES department_template_roles(template_id, role_key)
```

#### インスタンス層の制約

```sql
-- メンバー一意性
CONSTRAINT UNIQUE(instance_id, agent_id) ON department_instance_members

-- ワークフロー実行一意性
CONSTRAINT UNIQUE(instance_id, process_id, execution_count) 
  ON department_instance_workflows
```

### 5-4. マイグレーション戦略

```python
def initialize_department_templates():
    """部署テンプレートの初期化（冪等）"""
    conn = get_db_connection()
    
    # テーブル存在確認 → 存在しなければ CREATE
    tables = [
        ('departments_templates', CREATE_DEPARTMENTS_TEMPLATES_SQL),
        ('department_template_roles', CREATE_DEPARTMENT_TEMPLATE_ROLES_SQL),
        ('department_template_processes', CREATE_DEPARTMENT_TEMPLATE_PROCESSES_SQL),
        ('department_template_tasks', CREATE_DEPARTMENT_TEMPLATE_TASKS_SQL),
        ('department_instances', CREATE_DEPARTMENT_INSTANCES_SQL),
        ('department_instance_members', CREATE_DEPARTMENT_INSTANCE_MEMBERS_SQL),
        ('department_instance_workflows', CREATE_DEPARTMENT_INSTANCE_WORKFLOWS_SQL),
    ]
    
    for table_name, create_sql in tables:
        if not table_exists(conn, table_name):
            conn.execute(create_sql)
    
    # 初期テンプレートデータ投入
    insert_default_department_templates(conn)
    
    conn.commit()
```

---

## 附録: CREATE文完全版

### A-1. テンプレート層CREATE文

```sql
-- 部署テンプレート定義
CREATE TABLE IF NOT EXISTS departments_templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    category        TEXT NOT NULL,
    version         INTEGER DEFAULT 1,
    status          TEXT DEFAULT 'draft',
    total_roles     INTEGER DEFAULT 0,
    total_processes INTEGER DEFAULT 0,
    total_tasks     INTEGER DEFAULT 0,
    config          TEXT,
    created_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    CHECK(status IN ('draft', 'active', 'deprecated')),
    CHECK(category IN ('back-office', 'tech', 'ops', 'support'))
);

CREATE INDEX IF NOT EXISTS idx_departments_templates_status 
  ON departments_templates(status);
CREATE INDEX IF NOT EXISTS idx_departments_templates_category 
  ON departments_templates(category);

-- ロール定義
CREATE TABLE IF NOT EXISTS department_template_roles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL REFERENCES departments_templates(id) ON DELETE CASCADE,
    role_key         TEXT NOT NULL,
    role_label       TEXT NOT NULL,
    role_order       INTEGER NOT NULL,
    responsibility   TEXT,
    required_skills  TEXT,
    min_members      INTEGER DEFAULT 1,
    max_members      INTEGER,
    supervisor_role_key TEXT,
    config           TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, role_key),
    UNIQUE(template_id, role_order),
    CHECK(min_members >= 1),
    CHECK(max_members IS NULL OR max_members >= min_members)
);

CREATE INDEX IF NOT EXISTS idx_department_template_roles_template_id 
  ON department_template_roles(template_id);

-- プロセス定義
CREATE TABLE IF NOT EXISTS department_template_processes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL REFERENCES departments_templates(id) ON DELETE CASCADE,
    process_key      TEXT NOT NULL,
    process_label    TEXT NOT NULL,
    process_order    INTEGER NOT NULL,
    description      TEXT,
    responsible_role_key TEXT NOT NULL,
    estimated_hours  INTEGER,
    frequency        TEXT,
    doc_requirements TEXT,
    config           TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, process_key),
    UNIQUE(template_id, process_order),
    CHECK(frequency IN ('daily', 'weekly', 'monthly', 'quarterly', 'annual', 'ad-hoc'))
);

CREATE INDEX IF NOT EXISTS idx_department_template_processes_template_id 
  ON department_template_processes(template_id);

-- タスク定義
CREATE TABLE IF NOT EXISTS department_template_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id        INTEGER NOT NULL REFERENCES department_template_processes(id) ON DELETE CASCADE,
    template_id       INTEGER NOT NULL REFERENCES departments_templates(id) ON DELETE CASCADE,
    task_key          TEXT NOT NULL,
    task_title        TEXT NOT NULL,
    task_description  TEXT,
    assigned_role_key TEXT NOT NULL,
    category          TEXT,
    estimated_hours   REAL,
    depends_on_key    TEXT,
    priority          INTEGER DEFAULT 3,
    success_criteria  TEXT,
    config            TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(process_id, task_key),
    CHECK(priority IN (1, 2, 3)),
    CHECK(estimated_hours > 0)
);

CREATE INDEX IF NOT EXISTS idx_department_template_tasks_process_id 
  ON department_template_tasks(process_id);
```

### A-2. インスタンス層CREATE文

```sql
-- 部署インスタンス
CREATE TABLE IF NOT EXISTS department_instances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id     INTEGER NOT NULL REFERENCES departments_templates(id),
    name            TEXT NOT NULL,
    status          TEXT DEFAULT 'active',
    organization_id TEXT,
    location        TEXT,
    manager_agent_id INTEGER REFERENCES agents(id),
    context         TEXT,
    member_count    INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    started_at      TEXT,
    closed_at       TEXT,
    CHECK(status IN ('planning', 'active', 'suspended', 'closed'))
);

CREATE INDEX IF NOT EXISTS idx_department_instances_template_id 
  ON department_instances(template_id);
CREATE INDEX IF NOT EXISTS idx_department_instances_status 
  ON department_instances(status);

-- メンバー割り当て
CREATE TABLE IF NOT EXISTS department_instance_members (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id      INTEGER NOT NULL REFERENCES department_instances(id) ON DELETE CASCADE,
    agent_id         INTEGER NOT NULL REFERENCES agents(id),
    role_key         TEXT NOT NULL,
    status           TEXT DEFAULT 'active',
    start_date       TEXT NOT NULL DEFAULT (date('now')),
    end_date         TEXT,
    assigned_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, agent_id),
    CHECK(status IN ('active', 'inactive', 'on-leave'))
);

CREATE INDEX IF NOT EXISTS idx_department_instance_members_instance_id 
  ON department_instance_members(instance_id);
CREATE INDEX IF NOT EXISTS idx_department_instance_members_agent_id 
  ON department_instance_members(agent_id);

-- プロセス実行ワークフロー
CREATE TABLE IF NOT EXISTS department_instance_workflows (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id           INTEGER NOT NULL REFERENCES department_instances(id) ON DELETE CASCADE,
    process_id            INTEGER NOT NULL REFERENCES department_template_processes(id),
    workflow_instance_id  INTEGER REFERENCES workflow_instances(id),
    execution_count       INTEGER DEFAULT 1,
    status                TEXT DEFAULT 'pending',
    scheduled_date        TEXT,
    started_at            TEXT,
    completed_at          TEXT,
    result_notes          TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, process_id, execution_count),
    CHECK(status IN ('pending', 'running', 'completed', 'failed', 'paused'))
);

CREATE INDEX IF NOT EXISTS idx_department_instance_workflows_instance_id 
  ON department_instance_workflows(instance_id);
CREATE INDEX IF NOT EXISTS idx_department_instance_workflows_status 
  ON department_instance_workflows(status);
```

---

## 参考資料

- **関連ドキュメント**: 
  - `data-model.md` - ワークフローテンプレートデータモデル
  - `workflow-template-design.md` - ワークフローテンプレート設計
  - `architecture-design.md` - システムアーキテクチャ
  
- **実装リポジトリ**:
  - `dashboard/models.py` - Pydanticモデル定義
  - `workflow/repositories/` - データアクセス層
  
- **テスト**:
  - `features/` - BDDテストシナリオ
  - `tests/` - ユニット・統合テスト

---

*このドキュメントは Tech Lead による設計仕様です。複数エンジニアが実装フェーズに並行着手できるよう、スキーマ・業務フロー・実装ガイドラインを完全に定義しています。*
