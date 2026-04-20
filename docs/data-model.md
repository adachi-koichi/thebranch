# ワークフローテンプレートシステム - データモデル設計

**作成日**: 2026-04-18  
**バージョン**: v1.0 (Phase 3)  
**対応**: workflow-template-design.md (Phase 2) の詳細化

---

## 目次

1. [エンティティ関係図 (ER)](#1-エンティティ関係図-er)
2. [テーブル詳細仕様](#2-テーブル詳細仕様)
3. [データフロー図](#3-データフロー図)
4. [整合性制約・バリデーション](#4-整合性制約バリデーション)

---

## 1. エンティティ関係図 (ER)

### 1-1. ER 図（ASCII アート）

```
┌──────────────────────────────────────────────────────────────────────┐
│                        ワークフロー層                                 │
│                                                                      │
│  ┌─────────────────────┐                    ┌──────────────────┐   │
│  │ workflow_templates  │                    │  wf_template_*   │   │
│  │                     │                    │    (nodes/edges) │   │
│  │ id (PK)             │◄──────1:N─────────►│ template_id(FK)  │   │
│  │ name                │                    │                  │   │
│  │ description         │                    └──────────────────┘   │
│  │ status              │                                            │
│  └─────────────────────┘                                            │
│          ▲                                                           │
│          │                                                           │
│          │ 1:N                                                       │
│          │                                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │        wf_template_phases  (新規)                           │   │
│  │                                                             │   │
│  │ id (PK)                    phase_order (実行順序)          │   │
│  │ template_id (FK)           specialist_type (pm/eng/qa/ops) │   │
│  │ phase_key                  task_count                      │   │
│  │ phase_label                is_parallel (前フェーズとの並列) │   │
│  └────────────────┬──────────────────────────────────────────┘   │
│                   │                                                │
│                   │ 1:N                                            │
│                   ▼                                                │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │      wf_template_tasks  (新規)                           │    │
│  │                                                          │    │
│  │ id (PK)             task_key (テンプレート内一意)      │    │
│  │ phase_id (FK)       task_title                          │    │
│  │ template_id (FK)    task_description (プレースホルダ対応) │    │
│  │ category            depends_on_key (同一フェーズ内依存)  │    │
│  │ estimated_hours     priority                            │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                       インスタンス層                                   │
│                                                                      │
│  ┌──────────────────────┐          ┌────────────────────────────┐  │
│  │ workflow_instances   │          │ workflow_instance_         │  │
│  │                      │◄─1:N────►│ specialists  (新規)        │  │
│  │ id (PK)              │          │                            │  │
│  │ template_id (FK)─────┼─────────►│ instance_id (FK)           │  │
│  │ name                 │          │ phase_id (FK)              │  │
│  │ status               │          │ specialist_id (FK → agents)│  │
│  │ context (JSON)       │          │ specialist_slug            │  │
│  │ created_at           │          │ specialist_name            │  │
│  └──────┬───────────────┘          └────────────────────────────┘  │
│         │                                                           │
│         │ 1:N                                                       │
│         ▼                                                           │
│  ┌──────────────────────────────────────────────────┐              │
│  │    wf_instance_nodes  (既存・拡張)              │              │
│  │                                                  │              │
│  │ id (PK)               status (waiting/ready/...) │              │
│  │ instance_id (FK)      task_id (FK → dev_tasks)   │              │
│  │ template_node_id (FK) result (分岐判定用)        │              │
│  │ node_key              started_at / completed_at  │              │
│  │ node_type (task)      created_at                 │              │
│  └──────────────────────────────────────────────────┘              │
│         ▲                                                           │
│         │                                                           │
│         │ task_id (FK)                                              │
│         │                                                           │
└─────────┼───────────────────────────────────────────────────────────┘
          │
┌─────────┼───────────────────────────────────────────────────────────┐
│         │                      タスク層                              │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │            dev_tasks  (既存・拡張)                           │ │
│  │                                                              │ │
│  │ id (PK)             status (pending/in_progress/completed)  │ │
│  │ title               phase (phase_key)                        │ │
│  │ description         assignee (specialist_slug)              │ │
│  │ priority            practitioner_id (agents.id)             │ │
│  │ category            practitioner_status                     │ │
│  │ created_at / updated_at                                     │ │
│  └──────────────────────────────────────────────────────────────┘ │
│         ▲                                                           │
│         │                                                           │
│         │ 1:N (depends_on)                                         │
│         │                                                           │
│  ┌──────┴──────────────────────────────────────────────────────┐  │
│  │      task_dependencies  (既存)                              │  │
│  │                                                              │  │
│  │ task_id (FK → dev_tasks)      depends_on_id (FK → dev_tasks)  │  │
│  │ created_at                                                  │  │
│  │ UNIQUE(task_id, depends_on_id) UNIQUE制約                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                       ペルソナ・チーム層                              │
│                                                                      │
│  ┌─────────────────────────┐                                        │
│  │       agents  (既存)     │                                        │
│  │                         │                                        │
│  │ id (PK)                 │                                        │
│  │ name                    │                                        │
│  │ slug (unique)           │                                        │
│  │ role_type (em/engineer) │                                        │
│  │ specialty               │                                        │
│  └─────────────────────────┘                                        │
│          ▲                                                           │
│          │ specialist_id (FK)                                        │
│          │                                                           │
│  ┌──────────────────────────────────────────────────┐              │
│  │  workflow_instance_specialists  (新規)          │              │
│  │  ├─ specialist_id → agents.id                   │              │
│  │  └─ phase_id → wf_template_phases.id            │              │
│  └──────────────────────────────────────────────────┘              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 1-2. レイヤー別の特徴

| レイヤー | 主要テーブル | 役割 | 主キー | 外部キー |
|---------|---------|------|--------|--------|
| **テンプレート層** | workflow_templates | テンプレートの定義 | id | — |
| | wf_template_phases | フェーズの定義 | id | template_id |
| | wf_template_tasks | タスクの定義 | id | phase_id |
| **インスタンス層** | workflow_instances | テンプレートから生成したインスタンス | id | template_id |
| | workflow_instance_specialists | Specialist の割り当て | id | instance_id, specialist_id |
| | wf_instance_nodes | Phase インスタンス | id | instance_id, task_id |
| **タスク層** | dev_tasks | 実行タスク | id | phase, practitioner_id |
| | task_dependencies | タスク依存関係 | — | task_id, depends_on_id |
| **ペルソナ層** | agents | エージェント/ペルソナ | id | — |

---

## 2. テーブル詳細仕様

### 2-1. テンプレート層テーブル

#### `workflow_templates` - ワークフロー定義

```sql
CREATE TABLE IF NOT EXISTS workflow_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,           -- 例: "Product Launch"
    description TEXT,                           -- テンプレート説明
    version     INTEGER DEFAULT 1,              -- バージョン管理
    status      TEXT DEFAULT 'draft',           -- draft / active / deprecated
    created_by  TEXT,                           -- 作成者（ユーザー名）
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_workflow_templates_status ON workflow_templates(status);
CREATE INDEX IF NOT EXISTS idx_workflow_templates_created_at ON workflow_templates(created_at);
```

**カラム説明**:
- `name`: テンプレートの一意な識別子。UI/CLI で参照される
- `version`: テンプレートの世代管理。同名テンプレートの異版は別レコード
- `status`: テンプレートのライフサイクル（draft=編集可能, active=利用可能, deprecated=廃止予定）

#### `wf_template_phases` - フェーズ定義

```sql
CREATE TABLE IF NOT EXISTS wf_template_phases (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL REFERENCES workflow_templates(id),
    phase_key        TEXT NOT NULL,             -- 例: 'planning', 'development', 'testing'
    phase_order      INTEGER NOT NULL,          -- 実行順序（1, 2, 3, ...）
    phase_label      TEXT NOT NULL,             -- 表示名（例: "Planning Phase"）
    specialist_type  TEXT NOT NULL,             -- 'pm', 'engineer', 'qa', 'devops', 'designer'
    task_count       INTEGER NOT NULL DEFAULT 0, -- このフェーズのタスク数
    description      TEXT,                      -- フェーズ説明
    estimated_hours  INTEGER,                   -- 見積もり時間
    is_parallel      BOOLEAN DEFAULT 0,         -- 前フェーズと並列実行可能か (1=可能, 0=順序)
    config           TEXT,                      -- JSON（追加設定）
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, phase_key),
    UNIQUE(template_id, phase_order)            -- 同一テンプレート内で phase_order は一意
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_wf_template_phases_template_id ON wf_template_phases(template_id);
CREATE INDEX IF NOT EXISTS idx_wf_template_phases_phase_order ON wf_template_phases(template_id, phase_order);
```

**カラム説明**:
- `phase_key`: テンプレート内で phase を一意に識別する（スネークケース推奨）
- `phase_order`: 1 から始まる実行順序。この順序で タスク生成・フェーズ遷移が行われる
- `is_parallel`: 前フェーズの完了を待たずに並列開始可能か（0=順序待ち, 1=並列可能）
- `config`: JSON（例：`{"retry_on_failure": true, "timeout_seconds": 3600}`）

#### `wf_template_tasks` - タスク定義

```sql
CREATE TABLE IF NOT EXISTS wf_template_tasks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_id         INTEGER NOT NULL REFERENCES wf_template_phases(id),
    template_id      INTEGER NOT NULL REFERENCES workflow_templates(id),
    task_key         TEXT NOT NULL,             -- 例: 'design-arch', 'implement-api'
    task_title       TEXT NOT NULL,             -- タスク表示名
    task_description TEXT,                      -- 説明（{specialist_name}, {phase_label} プレースホルダ対応）
    category         TEXT,                      -- 'design', 'implement', 'test', 'review' 等
    estimated_hours  INTEGER,                   -- 見積もり時間
    depends_on_key   TEXT,                      -- 依存タスクキー（同一フェーズ内）
    priority         INTEGER DEFAULT 3,         -- 優先度（1=高, 2=中, 3=低）
    config           TEXT,                      -- JSON（追加設定）
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(phase_id, task_key)                  -- 同一フェーズ内で task_key は一意
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_wf_template_tasks_phase_id ON wf_template_tasks(phase_id);
CREATE INDEX IF NOT EXISTS idx_wf_template_tasks_template_id ON wf_template_tasks(template_id);
```

**カラム説明**:
- `task_key`: phase_key + task_key で全体で一意な ID を構成
- `depends_on_key`: 同一 phase_id 内の別タスク task_key を参照。NULL=独立タスク
- `task_description`: プレースホルダ対応（`{specialist_name}` → 実際の specialist 名に置換）

---

### 2-2. インスタンス層テーブル

#### `workflow_instances` - ワークフローインスタンス

```sql
CREATE TABLE IF NOT EXISTS workflow_instances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id     INTEGER NOT NULL REFERENCES workflow_templates(id),
    name            TEXT NOT NULL,              -- 例: "Product Launch #1"
    status          TEXT DEFAULT 'pending',     -- pending / running / completed / failed / paused
    project         TEXT,                       -- プロジェクト名
    context         TEXT,                       -- JSON（実行時変数、specialist_assignments 等）
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    started_at      TEXT,                       -- フロー開始時刻
    completed_at    TEXT                        -- フロー完了時刻
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_workflow_instances_template_id ON workflow_instances(template_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_status ON workflow_instances(status);
CREATE INDEX IF NOT EXISTS idx_workflow_instances_created_at ON workflow_instances(created_at);
```

**カラム説明**:
- `context`: JSON 形式の実行時変数（例：`{"specialist_assignments": {...}, "custom_vars": {...}}`)
- `status`: インスタンス全体のステータス（phase ノードの status とは別）

#### `workflow_instance_specialists` - Specialist アサイン

```sql
CREATE TABLE IF NOT EXISTS workflow_instance_specialists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id       INTEGER NOT NULL REFERENCES workflow_instances(id),
    phase_id          INTEGER NOT NULL REFERENCES wf_template_phases(id),
    phase_key         TEXT NOT NULL,            -- キャッシュ用
    specialist_id     INTEGER NOT NULL REFERENCES agents(id),
    specialist_slug   TEXT NOT NULL,            -- agents.slug （例: "em-alice"）
    specialist_name   TEXT NOT NULL,            -- agents.name （表示用）
    specialist_role   TEXT NOT NULL,            -- agents.role_type （'em', 'engineer', 'qa'）
    assigned_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, phase_id)               -- 1 instance/1 phase に対して 1 specialist のみ
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_workflow_instance_specialists_instance_id 
  ON workflow_instance_specialists(instance_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_specialists_specialist_id 
  ON workflow_instance_specialists(specialist_id);
```

**カラム説明**:
- `specialist_slug` / `specialist_name`: agents テーブルのキャッシュ（インスタンス作成時点のスナップショット）
- `UNIQUE(instance_id, phase_id)`: 1 インスタンス内で同一 phase に複数 specialist を割り当てない（現仕様）

---

### 2-3. タスク層テーブル（既存の拡張）

#### `dev_tasks` - 実行タスク（拡張カラム）

```sql
-- 既存テーブルに以下カラムを追加する場合
ALTER TABLE dev_tasks ADD COLUMN phase TEXT;                 -- フェーズキー
ALTER TABLE dev_tasks ADD COLUMN workflow_instance_id INTEGER; -- 所属インスタンス ID
ALTER TABLE dev_tasks ADD COLUMN wf_node_key TEXT;           -- wf_instance_nodes.node_key へのリンク

-- インデックス
CREATE INDEX IF NOT EXISTS idx_dev_tasks_workflow_instance_id 
  ON dev_tasks(workflow_instance_id);
CREATE INDEX IF NOT EXISTS idx_dev_tasks_phase ON dev_tasks(phase);
```

**既存カラム（Phase 1 で存在）**:
- `id`, `title`, `description`, `status`, `priority`, `category`, `assignee`, `practitioner_id`, `created_at`, `updated_at`

**拡張カラム（Phase 3 で追加）**:
- `phase`: wf_template_phases.phase_key へのリンク（タスク参照時にフェーズを特定）
- `workflow_instance_id`: workflow_instances.id （タスクがどのワークフローに属するかを追跡）
- `wf_node_key`: wf_instance_nodes.node_key へのリンク（双方向参照の確保）

---

## 3. データフロー図

### 3-1. テンプレート→インスタンス→タスク生成のデータフロー

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. テンプレート定義                                              │
│                                                                 │
│ workflow_templates (テンプレート本体)                           │
│  ↓                                                              │
│ wf_template_phases (複数フェーズ, phase_order でソート)        │
│  ↓                                                              │
│ wf_template_tasks (各フェーズのタスク定義)                     │
└─────────────────────────────────────────────────────────────────┘
         ↓ インスタンス化
┌─────────────────────────────────────────────────────────────────┐
│ 2. インスタンス化（API 呼び出し）                                │
│                                                                 │
│ Input: template_id, instance_name, specialist_assignments      │
│        {phase_key → specialist_id}                             │
│                                                                 │
│ ① workflow_instances レコード作成（status=pending）            │
│ ② workflow_instance_specialists に specialist マッピング記録    │
│ ③ wf_instance_nodes（phase node）を生成                       │
│    └─ 初期 status=waiting                                      │
└─────────────────────────────────────────────────────────────────┘
         ↓ タスク自動生成
┌─────────────────────────────────────────────────────────────────┐
│ 3. 自動タスク生成                                                │
│                                                                 │
│ For each phase (sorted by phase_order):                        │
│                                                                 │
│   ① wf_template_tasks を読み込み                              │
│   ② Specialist 情報を workflow_instance_specialists から取得   │
│   ③ dev_tasks を作成（title, description, assignee 等）       │
│   ④ task_dependencies に依存関係を記録                         │
│      ├─ Phase内依存：depends_on_key から解決                  │
│      └─ フェーズ間依存：前フェーズのすべてのタスクに依存        │
│   ⑤ wf_instance_nodes.task_id に dev_tasks.id をリンク        │
│      └─ node status=ready に遷移                               │
│                                                                 │
│ Result:                                                         │
│   - dev_tasks テーブルに T = Σ(task_count) 件の新規レコード   │
│   - task_dependencies テーブルに依存関係エッジを記録            │
│   - wf_instance_nodes の task_id が全て埋まる                 │
└─────────────────────────────────────────────────────────────────┘
         ↓ 実行開始
┌─────────────────────────────────────────────────────────────────┐
│ 4. ワークフロー実行                                              │
│                                                                 │
│ workflow_instances status=running に遷移 (started_at 記録)    │
│ Phase インスタンスが waiting → ready → running → completed      │
│ タスクが pending → in_progress → completed に遷移              │
│                                                                 │
│ task_dependencies に従い、依存タスク完了後に後続タスク利用可能  │
│ unblock_successors() で自動的に blocked → pending に遷移      │
└─────────────────────────────────────────────────────────────────┘
```

### 3-2. テーブル間の数値関係

```
1 template
  ├─ N phases (wf_template_phases)
  │   └─ phase_order = 1, 2, 3, ...
  │
  ├─ M tasks (wf_template_tasks)
  │   └─ 各 task_key は (phase_id, task_key) で一意
  │
  └─ K instances (workflow_instances)
      └─ 1 instance
          ├─ N phase nodes (wf_instance_nodes)
          │   └─ 1 node ← 1 phase
          │
          ├─ N specialist assignments (workflow_instance_specialists)
          │   └─ 1 assignment ← 1 phase
          │
          └─ T tasks (dev_tasks)
              └─ T = Σ(phase.task_count) for all phases
              └─ 依存関係エッジ数 = Σ(フェーズ間依存) + Σ(フェーズ内依存)
```

**計算例（Product Launch テンプレート）**:
```
phases:
  - Planning (4 tasks)
  - Development (6 tasks)
  - Testing (5 tasks)
  - Deployment (3 tasks)

Total tasks per instance = 4 + 6 + 5 + 3 = 18 tasks

Dependency edges:
  - Phase間依存: Planning→Dev (4×6=24 edges)
              + Dev→Test (6×5=30 edges)
              + Test→Deploy (5×3=15 edges)
  - Phase内依存: 設計に依存 (1 edge/phase × 4 phases = 4 edges)

Total dependency edges ≈ 24 + 30 + 15 + 4 = 73 edges
```

---

## 4. 整合性制約・バリデーション

### 4-1. テンプレート層の制約

| 制約 | SQL/ロジック | 理由 |
|-----|---------|------|
| **phase_key 一意性** | `UNIQUE(template_id, phase_key)` | 同一テンプレート内で phase を一意に識別 |
| **phase_order 一意性** | `UNIQUE(template_id, phase_order)` | 実行順序の明確化・スキップ防止 |
| **phase_order >= 1** | `CHECK(phase_order >= 1)` | 順序は 1 から開始 |
| **task_key 一意性** | `UNIQUE(phase_id, task_key)` | 同一フェーズ内で task を一意に識別 |
| **depends_on_key 検証** | `depends_on_key IS NULL OR EXISTS(SELECT 1 FROM wf_template_tasks WHERE phase_id=? AND task_key=?)` | 存在する task を参照 |
| **循環依存検出** | BFS / グラフアルゴリズム（KuzuDB） | DAG 検証（task_dependencies レベル） |

### 4-2. インスタンス層の制約

| 制約 | SQL/ロジック | 理由 |
|-----|---------|------|
| **specialist_id 存在確認** | `CHECK(specialist_id IN (SELECT id FROM agents))` | 有効な specialist のみ割り当て |
| **instance/phase 一意性** | `UNIQUE(instance_id, phase_id)` | 1 phase に対して 1 specialist のみ |
| **template_id 有効性** | `FOREIGN KEY(template_id)` | テンプレート削除時に cascade 削除を検討 |
| **specialist_assignments 完全性** | Python: `count(assignments) == count(phases)` | インスタンス化時にすべての phase に specialist を割り当て |

### 4-3. タスク層の制約

| 制約 | SQL/ロジック | 理由 |
|-----|---------|------|
| **task_dependencies 循環検出** | KuzuDB `has_cycle()` | DAG を維持 |
| **depends_on_id 存在確認** | `FOREIGN KEY(depends_on_id) REFERENCES dev_tasks(id)` | 有効なタスクを参照 |
| **status 遷移検証** | Python `validate_transition()` (既存) | ステートマシンで不正遷移を防止 |
| **phase カラム値** | `phase IN (SELECT phase_key FROM wf_template_phases WHERE template_id=?)` | 有効なフェーズキーのみ |

### 4-4. プレースホルダ置換バリデーション

```python
# タスク生成時に実行
def validate_task_description(template: str, context: dict) -> bool:
    """
    task_description テンプレート内のプレースホルダがすべて context で解決可能か検証
    
    Args:
        template: "{specialist_name} が実装します"
        context: {"specialist_name": "Alice", "phase_label": "Development"}
    
    Returns:
        True = 全プレースホルダが解決可能
    """
    import re
    placeholders = re.findall(r'\{(\w+)\}', template)
    for ph in placeholders:
        if ph not in context:
            raise ValueError(f"Placeholder '{ph}' not found in context")
    return True
```

---

## 5. スキーママイグレーション

### 5-1. Phase 3 で追加するテーブル・カラム

```sql
-- T1: wf_template_phases テーブル作成
CREATE TABLE IF NOT EXISTS wf_template_phases (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL REFERENCES workflow_templates(id),
    phase_key        TEXT NOT NULL,
    phase_order      INTEGER NOT NULL,
    phase_label      TEXT NOT NULL,
    specialist_type  TEXT NOT NULL,
    task_count       INTEGER NOT NULL DEFAULT 0,
    description      TEXT,
    estimated_hours  INTEGER,
    is_parallel      BOOLEAN DEFAULT 0,
    config           TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, phase_key),
    UNIQUE(template_id, phase_order)
);

-- T2: wf_template_tasks テーブル作成
CREATE TABLE IF NOT EXISTS wf_template_tasks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_id         INTEGER NOT NULL REFERENCES wf_template_phases(id),
    template_id      INTEGER NOT NULL REFERENCES workflow_templates(id),
    task_key         TEXT NOT NULL,
    task_title       TEXT NOT NULL,
    task_description TEXT,
    category         TEXT,
    estimated_hours  INTEGER,
    depends_on_key   TEXT,
    priority         INTEGER DEFAULT 3,
    config           TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(phase_id, task_key)
);

-- T3: workflow_instance_specialists テーブル作成
CREATE TABLE IF NOT EXISTS workflow_instance_specialists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id       INTEGER NOT NULL REFERENCES workflow_instances(id),
    phase_id          INTEGER NOT NULL REFERENCES wf_template_phases(id),
    phase_key         TEXT NOT NULL,
    specialist_id     INTEGER NOT NULL REFERENCES agents(id),
    specialist_slug   TEXT NOT NULL,
    specialist_name   TEXT NOT NULL,
    specialist_role   TEXT NOT NULL,
    assigned_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, phase_id)
);

-- C1-C3: dev_tasks に カラム追加
ALTER TABLE dev_tasks ADD COLUMN phase TEXT;
ALTER TABLE dev_tasks ADD COLUMN workflow_instance_id INTEGER;
ALTER TABLE dev_tasks ADD COLUMN wf_node_key TEXT;
```

### 5-2. マイグレーション検証（冪等性）

```python
def ensure_schema():
    """スキーマが最新状態であることを保証（冪等）"""
    conn = get_db_connection()
    
    # 各テーブル存在確認 → 存在しなければ CREATE
    tables_to_create = [
        ('wf_template_phases', CREATE_WF_TEMPLATE_PHASES_SQL),
        ('wf_template_tasks', CREATE_WF_TEMPLATE_TASKS_SQL),
        ('workflow_instance_specialists', CREATE_WORKFLOW_INSTANCE_SPECIALISTS_SQL),
    ]
    
    for table_name, create_sql in tables_to_create:
        if not table_exists(conn, table_name):
            conn.execute(create_sql)
    
    # カラム追加（存在確認）
    if not column_exists(conn, 'dev_tasks', 'phase'):
        conn.execute("ALTER TABLE dev_tasks ADD COLUMN phase TEXT")
    
    conn.commit()
```

---

*このドキュメントは、Phase 2 の概念設計を Phase 3 向けにデータモデルとして具体化したものです。*
*次ステップ：architecture-design.md（システムアーキテクチャ）および flow-design.md（処理フロー）を参照。*
