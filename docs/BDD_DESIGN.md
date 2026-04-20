# BDD 業務フロー高水準設計 - THEBRANCH

**作成日**: 2026-04-19  
**バージョン**: v1.0  
**対象**: THEBRANCH プロジェクト全体の業務フロー・データモデル・エージェント間通信設計

---

## 目次

1. [BDD 業務フロー概要](#1-bdd-業務フロー概要)
2. [ビジネスプロセス高水準フロー](#2-ビジネスプロセス高水準フロー)
3. [データモデル・エンティティ設計](#3-データモデルエンティティ設計)
4. [エージェント間通信・シーケンス図](#4-エージェント間通信シーケンス図)
5. [同時起動数制限ルール実装](#5-同時起動数制限ルール実装)
6. [エラーハンドリング・リカバリーフロー](#6-エラーハンドリングリカバリーフロー)
7. [監視・ヘルスチェック・異常検知](#7-監視ヘルスチェック異常検知)
8. [実装チェックリスト](#8-実装チェックリスト)

---

## 1. BDD 業務フロー概要

### 1-1. BDD（Behavior Driven Development）の文脈

THEBRANCH は **BDD の "Behavior Driven" 理念**を実装したマルチエージェントシステム。

- **Behavior**: 複数の Claude インスタンスが협力して、プロダクトの要件を満たすよう振る舞う
- **Driven**: orchestrator が各エージェント（PM / EM / Engineer）の動きを監視・駆動
- **Development**: workflow template による体系的なタスク設計・割り当て・実行

### 1-2. 主要なアクター

| アクター | 役割 | tmux 配置 | 同時起動制限 |
|---------|------|---------|-----------|
| **Orchestrator** | 全エージェント監視・タスク委譲 | `ai-orchestrator@main:0.0` | 1（固定） |
| **PM / EM** | チーム管理・EM または Engineer チーム起動 | `{service}_orchestrator_wf{NNN}_{team}@main:managers` | 2 pane/window |
| **Engineer** | 実装・テスト・マージ | `{service}_orchestrator_wf{NNN}_{team}@main:members` | 3 pane/window |
| **External Systems** | GitHub / Discord / task-manager-sqlite | REST API / Webhook | N/A |

---

## 2. ビジネスプロセス高水準フロー

### 2-1. 全体ワークフロー（6段階）

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          START: User Request                             │
│                 (タスク作成 / プロジェクト起動要求)                        │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │                                       │
    Stage 1: Planning                    [Orchestrator Loop]
    (Design / Analysis)                      │
         │                              ┌──────▼────────┐
         │                              │ 3分間隔ポーリング │
         │                              │ pending task   │
         │                              │ 検出→start_pane │
         │                              └──────┬────────┘
         │                                     │
    ┌────▼─────────────────────────────────────▼─────────────────┐
    │ Stage 2: Team Initialization (Pane Creation)               │
    │                                                             │
    │ orchestrator: start_pane.py でチームセッション生成          │
    │  → {service}_orchestrator_wf{NNN}_{team}@main              │
    │      ├─ window:managers (PM / EM を起動)                   │
    │      └─ window:members (Engineer 準備)                     │
    │                                                             │
    │ PM/EM: tmux pane 内で ccc-engineering-manager 起動         │
    └────┬─────────────────────────────────────────────────────┬─┘
         │                                                     │
         │ [PM/EM Phase]                  [EM Phase]          │
    ┌────▼────────────────────────┐  ┌────────────────────┐  │
    │ Stage 3: Task Delegation    │  │ (or combined role) │  │
    │                             │  │                    │  │
    │ workflow template の読込    │  └────────────────────┘  │
    │ ↓                           │                          │
    │ Phase / Task 分析          │ Engineer チーム起動      │
    │ ↓                           │  (最大3名)              │
    │ start_pane.py で           │                          │
    │ Engineer チーム起動         │                          │
    └────┬────────────────────────┴──────────────────────────┘
         │
    ┌────▼──────────────────────────────────────────────────────┐
    │ Stage 4: Task Execution (Engineer Phase)                 │
    │                                                           │
    │ ┌─────────────────┐  ┌─────────────────┐               │
    │ │  Engineer #1    │  │  Engineer #2    │               │
    │ │  (members:0)    │  │  (members:1)    │               │
    │ │                 │  │                 │               │
    │ │ - Task 実装     │  │ - Task 実装     │               │
    │ │ - テスト実行    │  │ - テスト実行    │               │
    │ │ - PR 作成       │  │ - PR 作成       │               │
    │ │ - タスク完了報告│  │ - タスク完了報告│               │
    │ └────────┬────────┘  └────────┬────────┘               │
    │          │                     │                        │
    │          │ task.py update      │ task.py update         │
    │          │ --status completed  │ --status completed     │
    │          └──────────┬──────────┘                        │
    │                     │                                   │
    │         taskList: pending → unblocked tasks             │
    │                     │                                   │
    │                     ▼                                   │
    │         [Next tasks to assign]                          │
    └────┬────────────────────────────────────────────────────┘
         │
         │ (All tasks completed)
         │
    ┌────▼──────────────────────────────────────────────────────┐
    │ Stage 5: Review / Merge (PM/EM Phase)                    │
    │                                                           │
    │ PR Review → GitHub Merge → Release                       │
    │ Workflow Instance Status → 'completed'                   │
    │ task-manager-sqlite に完了報告                             │
    └────┬──────────────────────────────────────────────────────┘
         │
    ┌────▼──────────────────────────────────────────────────────┐
    │ Stage 6: Cleanup (Orchestrator)                          │
    │                                                           │
    │ - チームセッション終了                                     │
    │ - リソース解放                                             │
    │ - 次タスク検出（goto Stage 1）                             │
    └────────────────────────────────────────────────────────────┘
```

### 2-2. Swimlane 図（役割別フロー）

```
Orchestrator              PM/EM                   Engineer          External (GitHub/API)
     │                     │                         │                       │
     │ [LOOP 3min]         │                         │                       │
     │ pending task        │                         │                       │
     │ 検出               │                         │                       │
     │                     │                         │                       │
     ├─ validate           │                         │                       │
     │  task schema        │                         │                       │
     │                     │                         │                       │
     ├─ start_pane.py      │                         │                       │
     │  (session create)   │                         │                       │
     │                     │                         │                       │
     └─────────────────────┼─ ccc-engineering-manager                       │
     │                     │  started                │                       │
     │                     │                         │                       │
     │ [monitor]           ├─ task.py list          │                       │
     │                     │  --status pending       │                       │
     │                     │                         │                       │
     │                     ├─ generate next          │                       │
     │                     │  tasks (workflow)       │                       │
     │                     │                         │                       │
     │                     ├─ start_pane.py         │                       │
     │                     │  (engineer launch)     │                       │
     │                     │                         │                       │
     │ [monitor]           │                         ├─ ccc started          │
     │                     │                         │                       │
     │                     │                         ├─ task.py show <ID>    │
     │                     │                         │                       │
     │                     │                         ├─ [CODE WORK]          │
     │                     │                         │  - design              │
     │                     │                         │  - implement           │
     │                     │                         │  - test                │
     │                     │                         │  - commit              │
     │                     │                         │                       │
     │                     │                         ├─ git push             │
     │                     │                         ├─────────────────────►│
     │                     │                         │                  PR creation
     │                     │                         │                       │
     │                     │                         ├─ task.py update      │
     │                     │                         │  --status completed    │
     │                     │                         │                       │
     │ [detect task done]  │                         │                       │
     │ unblocked tasks     │◄─────────────────────────────────────────────┤
     │ appear              │                                    [webhook]   │
     │                     │                                               │
     ├─ dispatch to        │                                               │
     │  idle engineers     │                                               │
     │                     │                                               │
     ├─ [LOOP CONTINUE]    │                                               │
     │                     │                                               │
     └─────────────────────┴─────────────────────────────────────────────┘
      [END: all tasks completed, session cleanup]
```

### 2-3. フェーズ依存関係フロー

```
Workflow Template Definition:
    │
    ├─ Phase 1: Planning
    │   ├─ Task 1.1: Design        (specialist: product-designer)
    │   └─ Task 1.2: Analysis       (specialist: product-manager)
    │       │
    │       └─ depends_on: [Task 1.1]
    │
    ├─ Phase 2: Implementation
    │   ├─ Task 2.1: Backend        (specialist: backend-engineer)
    │   ├─ Task 2.2: Frontend       (specialist: frontend-engineer)
    │   └─ Task 2.3: Integration    (specialist: qa-engineer)
    │       │
    │       └─ depends_on: [Task 2.1, Task 2.2]
    │
    └─ Phase 3: Release
        ├─ Task 3.1: Code Review    (specialist: tech-lead)
        ├─ Task 3.2: Release        (specialist: devops-engineer)
        └─ Task 3.3: Monitor        (specialist: ops-engineer)
            │
            └─ depends_on: [Task 3.1, Task 3.2]

Instance Execution:
    Phase 1: waiting
       ↓ (assign specialist → advance_wf_instance)
    Phase 1: ready
       ↓ (first task starts)
    Phase 1: running
       ↓ (Task 1.1 done)
    Phase 1.1: completed
       ↓ (Task 1.2 unblocked)
    Phase 1: running (Task 1.2)
       ↓ (Task 1.2 done)
    Phase 1: completed
       ↓ (unblock Phase 2)
    Phase 2: waiting → ready → running
       ↓ ...
    Phase 3: completed
       ↓
    Workflow Instance: completed
```

---

## 3. データモデル・エンティティ設計

### 3-1. ER 図（Entity Relationship Diagram）

```
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow Template Layer                       │
│                                                                 │
│  ┌────────────────────┐     ┌───────────────────────┐          │
│  │ workflow_templates │     │ wf_template_phases    │          │
│  ├────────────────────┤     ├───────────────────────┤          │
│  │ id (PK)           │◄────┤ id (PK)              │          │
│  │ name              │ 1:N  │ template_id (FK)     │          │
│  │ description       │     │ phase_order          │          │
│  │ created_at        │     │ phase_key            │          │
│  │ updated_at        │     │ phase_name           │          │
│  │ spec_version      │     │ specialist_role      │          │
│  └────────────────────┘     │ created_at           │          │
│                             └────────┬─────────────┘          │
│                                      │                         │
│                                      │ 1:N                     │
│                                      ▼                         │
│  ┌─────────────────────────────┐                             │
│  │ wf_template_tasks           │                             │
│  ├─────────────────────────────┤                             │
│  │ id (PK)                     │                             │
│  │ template_id (FK)            │                             │
│  │ phase_id (FK)               │                             │
│  │ task_key                    │                             │
│  │ task_title                  │                             │
│  │ task_description            │                             │
│  │ depends_on_keys (JSON/list) │                             │
│  │ task_order                  │                             │
│  │ created_at                  │                             │
│  └─────────────────────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
         ▲
         │
         │ instantiate
         │
┌────────┴─────────────────────────────────────────────────────────┐
│                    Workflow Instance Layer                        │
│                                                                  │
│  ┌──────────────────────┐     ┌───────────────────────┐         │
│  │ workflow_instances   │     │ wf_instance_nodes     │         │
│  ├──────────────────────┤     ├───────────────────────┤         │
│  │ id (PK)             │◄────┤ id (PK)              │         │
│  │ template_id (FK)    │ 1:N  │ instance_id (FK)     │         │
│  │ name                │     │ node_key             │         │
│  │ context (JSON)      │     │ node_type (phase)    │         │
│  │ status              │     │ status               │         │
│  │ created_at          │     │ phase_id (template)  │         │
│  │ updated_at          │     │ started_at           │         │
│  │                     │     │ completed_at         │         │
│  └──────────┬──────────┘     └─────────┬─────────────┘         │
│             │                          │                        │
│             │ 1:N                      │ 1:N                    │
│             │                          ▼                        │
│             │          ┌────────────────────────────────────┐  │
│             │          │ dev_tasks / project_tasks         │  │
│             │          ├────────────────────────────────────┤  │
│             │          │ id (PK)                           │  │
│             │          │ instance_id (FK)                  │  │
│             │          │ phase (workflow instance ref)     │  │
│             │          │ task_title                        │  │
│             │          │ description                       │  │
│             │          │ assigned_to (engineer UUID)       │  │
│             │          │ status (pending → completed)      │  │
│             │          │ depends_on_ids (FK list)          │  │
│             │          │ created_at / completed_at         │  │
│             │          └────────────────────────────────────┘  │
│             │                                                   │
│             └──────────────────┬────────────────────────────────┤
│                                │ insert → auto-generate         │
└────────────────────────────────┴────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Specialist Assignment Layer                   │
│                                                                 │
│  ┌──────────────────────────────┐                              │
│  │ workflow_instance_specialists│                              │
│  ├──────────────────────────────┤                              │
│  │ id (PK)                      │                              │
│  │ instance_id (FK)             │                              │
│  │ phase_id (FK)                │                              │
│  │ specialist_id (UUID)         │                              │
│  │ specialist_slug              │                              │
│  │ specialist_name              │                              │
│  │ assigned_at                  │                              │
│  └──────────────────────────────┘                              │
│                                                                 │
│  ┌──────────────────────────────┐                              │
│  │ specialists                  │                              │
│  ├──────────────────────────────┤                              │
│  │ id (PK, UUID)               │                              │
│  │ slug                         │                              │
│  │ name (display name)          │                              │
│  │ roles (JSON)                 │                              │
│  │ bio / description            │                              │
│  │ is_active                    │                              │
│  │ created_at                   │                              │
│  └──────────────────────────────┘                              │
└──────────────────────────────────────────────────────────────────┘
```

### 3-2. テーブル仕様（主要テーブル）

#### workflow_templates
```sql
CREATE TABLE workflow_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  spec_version TEXT DEFAULT '1.0',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### wf_template_phases
```sql
CREATE TABLE wf_template_phases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id INTEGER NOT NULL,
  phase_order INTEGER NOT NULL,
  phase_key TEXT NOT NULL,
  phase_name TEXT NOT NULL,
  specialist_role TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (template_id) REFERENCES workflow_templates(id),
  UNIQUE (template_id, phase_order)
);
```

#### wf_template_tasks
```sql
CREATE TABLE wf_template_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id INTEGER NOT NULL,
  phase_id INTEGER NOT NULL,
  task_key TEXT NOT NULL,
  task_title TEXT NOT NULL,
  task_description TEXT,
  depends_on_keys TEXT,  -- JSON array of task_key strings
  task_order INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (template_id) REFERENCES workflow_templates(id),
  FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id)
);
```

#### workflow_instances
```sql
CREATE TABLE workflow_instances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  context TEXT,  -- JSON context variables
  status TEXT DEFAULT 'pending',  -- pending, ready, running, completed, failed
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (template_id) REFERENCES workflow_templates(id)
);
```

#### wf_instance_nodes
```sql
CREATE TABLE wf_instance_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instance_id INTEGER NOT NULL,
  node_key TEXT NOT NULL,
  node_type TEXT DEFAULT 'phase',  -- phase, task
  status TEXT DEFAULT 'waiting',  -- waiting, ready, running, completed
  phase_id INTEGER,
  task_id INTEGER,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (instance_id) REFERENCES workflow_instances(id),
  FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id),
  UNIQUE (instance_id, node_key)
);
```

#### dev_tasks (auto-generated from workflow)
```sql
CREATE TABLE dev_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instance_id INTEGER NOT NULL,
  phase TEXT NOT NULL,
  task_title TEXT NOT NULL,
  description TEXT,
  assigned_to TEXT,  -- engineer UUID or NULL
  status TEXT DEFAULT 'pending',
  depends_on_ids TEXT,  -- JSON array
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  FOREIGN KEY (instance_id) REFERENCES workflow_instances(id)
);
```

#### workflow_instance_specialists
```sql
CREATE TABLE workflow_instance_specialists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instance_id INTEGER NOT NULL,
  phase_id INTEGER NOT NULL,
  specialist_id TEXT NOT NULL,  -- UUID
  specialist_slug TEXT,
  specialist_name TEXT,
  assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (instance_id) REFERENCES workflow_instances(id),
  FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id)
);
```

### 3-3. 状態遷移定義

#### Task Status State Machine
```
┌─────────┐
│pending  │ ← Task created, waiting for dependencies
└────┬────┘
     │ all dependencies met
     ▼
┌─────────┐
│ waiting │ ← Unblocked, ready to be assigned
└────┬────┘
     │ engineer claims task
     ▼
┌──────────────┐
│in_progress  │ ← Engineer working
└────┬────────┘
     │ engineer mark done
     ▼
┌──────────────┐
│reviewing     │ ← Optional: code review
└────┬────────┘
     │ reviewer approves
     ▼
┌──────────────┐
│completed     │ ← Task finished
└──────────────┘
     │
     └─► unblock dependent tasks
         (update status: pending → waiting)
```

#### Phase Status State Machine
```
┌─────────┐
│waiting  │ ← All phase tasks created, prev phase incomplete
└────┬────┘
     │ previous phase completes
     ▼
┌─────────┐
│ ready   │ ← Phase tasks available, specialist assigned
└────┬────┘
     │ first task starts
     ▼
┌──────────────┐
│running      │ ← Phase execution in progress
└────┬────────┘
     │ all tasks completed
     ▼
┌──────────────┐
│completed     │ ← Phase done, unblock next phase
└──────────────┘
```

#### Workflow Instance Status State Machine
```
┌─────────┐
│pending  │ ← Workflow created, not yet instantiated
└────┬────┘
     │ specialist assigned → advance_wf_instance
     ▼
┌─────────┐
│ ready   │ ← All phases created, tasks generated
└────┬────┘
     │ first phase task starts
     ▼
┌──────────────┐
│running      │ ← Workflow execution in progress
└────┬────────┘
     │ all phases completed
     ▼
┌──────────────┐
│completed     │ ← Workflow done
└──────────────┘
```

---

## 4. エージェント間通信・シーケンス図

### 4-1. Orchestrator → PM/EM → Engineer の委譲シーケンス

```
Orchestrator              PM/EM Session            Engineer Session      task-manager-sqlite
      │                        │                        │                      │
      │ 1. detect pending       │                        │                      │
      │    task #2065           │                        │                      │
      │                         │                        │                      │
      ├─ 2. validate            │                        │                      │
      │    task schema          │                        │                      │
      │                         │                        │                      │
      ├─ 3. start_pane.py       │                        │                      │
      │    --workflow-id 2065   │                        │                      │
      │    --role em            │                        │                      │
      │                         │                        │                      │
      │ 4. create tmux session  │                        │                      │
      │    {service}_orch.._wf.. │                        │                      │
      │                         │                        │                      │
      └────────────────────────►│ 5. ccc-engineering-manager                   │
      │                         │    starts              │                      │
      │                         │                        │                      │
      │ 6. [EM Loop - 3min]     │                        │                      │
      │                         ├─ 7. task.py list      │                      │
      │                         │     --status pending   │                      │
      │                         │                        │                      │
      │                         ├─ 8. fetch workflow    │                      │
      │                         │     template           │                      │
      │                         │                        │                      │
      │                         ├─ 9. generate next    │                      │
      │                         │     phase tasks       │                      │
      │                         │                        │                      │
      │                         ├─ 10. start_pane.py   │                      │
      │                         │      --role engineer  │                      │
      │                         │                        │                      │
      │ 11. [monitor]           │                        │ 12. ccc starts       │
      │                         │                        │                      │
      │                         │                        ├─ 13. task.py show   │
      │                         │                        │      <task_id>       │
      │                         │                        │                      │
      │                         │                        ├─ 14. [EXECUTE TASK]│
      │                         │                        │                      │
      │                         │                        │      ├─ design     │
      │                         │                        │      ├─ implement  │
      │                         │                        │      ├─ test       │
      │                         │                        │      ├─ commit     │
      │                         │                        │      └─ git push   │
      │                         │                        │                      │
      │                         │                        ├─ 15. task.py update│
      │                         │                        │      --status       │
      │                         │                        │      completed      │
      │                         │                        │                      │
      │                         │                        │ 16. → → → → → → → →│
      │                         │                        │     webhook fired  │
      │                         │◄───────────────────────┴─────────────────────┤
      │                         │      16b. new pending tasks                  │
      │                         │          (unblocked)                         │
      │                         │                                              │
      │ 17. poll unblocked      │                        │                      │
      │     tasks               │                        │                      │
      │                         │                        │                      │
      ├─ 18. assign next        │                        │                      │
      │      engineers           │                        │                      │
      │                         │                        │                      │
      └────────────────────────►│ 19. start_pane.py     │                      │
      │                         │     (new engineer)    │                      │
      │                         │                        │ 20. ccc starts      │
      │                         │                        │                      │
      │ [LOOP CONTINUES]        │                        │                      │
      │                         │                        │                      │
      └─────────────────────────┴────────────────────────┴──────────────────────┘
```

### 4-2. エージェント間メッセージングパターン

#### Pattern 1: Task Delegation (orchestrator → PM/EM)

```
Message Type: Task Delegation
From: orchestrator
To: PM/EM pane
Protocol: tmux send-keys / Discord DM / RemoteTrigger

Content:
{
  "type": "task_delegation",
  "task_id": 2065,
  "task_title": "BDD業務フロー設計",
  "instructions": "...",
  "workflow_template_id": 42,
  "deadline": "2026-04-20T00:00:00Z"
}

Expected Response:
- EM acknowledges (tmux capture-pane で確認)
- EM creates workflow instance
- EM starts engineer panes
```

#### Pattern 2: Task Assignment (PM/EM → Engineer)

```
Message Type: Task Assignment
From: PM/EM
To: Engineer pane
Protocol: tmux send-keys / message in ccc

Content:
{
  "type": "task_assignment",
  "task_id": 2065,
  "assigned_at": "2026-04-19T10:00:00Z",
  "instructions": "ref/task-assign.md 参照"
}

Expected Response:
- Engineer acknowledges (via ccc session)
- Engineer start working
- Engineer report progress every 30min (or task completion)
```

#### Pattern 3: Task Completion Report (Engineer → task-manager-sqlite)

```
Command: task.py update
From: Engineer
To: task-manager-sqlite
Protocol: subprocess / Python API

Command:
$ python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py \
    update 2065 \
    --status completed \
    --notes "設計ドキュメント完成、git commit済み"

Webhook Trigger:
- task-manager-sqlite 監視スクリプト
- unblocked_tasks を検出
- orchestrator に通知 (or polling で自動検出)
```

#### Pattern 4: Error Escalation (Any → Orchestrator)

```
Message Type: Error Escalation
From: PM/EM or Engineer
To: orchestrator (Discord DM / log aggregator)
Protocol: Discord / logging

Content:
{
  "severity": "critical|warning|info",
  "source": "PM/EM|Engineer",
  "session": "exp-stock_orchestrator_wf001_feature-x@main",
  "message": "エラー詳細",
  "action_required": true/false
}

Expected Response:
- orchestrator logs error
- orchestrator escalate to user (if action_required=true)
- orchestrator may auto-recover (if in CLAUDE.md)
```

---

## 5. 同時起動数制限ルール実装

### 5-1. 制限ルール定義

| ロール | 同時起動数 | 配置 | 備考 |
|--------|----------|------|------|
| **orchestrator** | 1 セッション | `ai-orchestrator@main:0:0` | 固定、変更禁止 |
| **PM/EM** | 2 pane/window | `{service}_orch_wf{NNN}_{team}@main:managers` | 同一ウィンドウ内 |
| **Engineer** | 3 pane/window | `{service}_orch_wf{NNN}_{team}@main:members` | 同一ウィンドウ内 |
| **チームセッション** | 複数展開可能 | 別々の session | 制限なし |

### 5-2. 実装フロー図

```
┌──────────────────────────────────────────────────────────────┐
│            start_pane.py (pane creation script)              │
│                                                              │
│ Input: --app <service>                                      │
│        --workflow-id <TASK_ID>                              │
│        --team <team-name>                                   │
│        --role <orchestrator|pm|em|engineer>                 │
│        --dir <path>                                         │
│        --message <instructions>                             │
└────────────────────┬─────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
    [orchestrator]         [pm/em/engineer]
        │                         │
        │ (自動ブロック)           │ ウィンドウ・ペイン作成
        │ 禁止操作検出            │
        │                         │
        ▼                         ▼
┌──────────────────────────────────────────────────────────────┐
│  validate_concurrency_limit(                                │
│    session_name: str,                                       │
│    window_name: str,                                        │
│    role: str                                                │
│  ) -> bool                                                  │
│                                                              │
│ 1. Count existing panes by role                            │
│ 2. Check against limit table:                              │
│    - orchestrator: 1 pane max in ai-orchestrator@main:0    │
│    - managers: 2 pane max per window                       │
│    - members: 3 pane max per window                        │
│ 3. Return True if under limit, False if exceeded           │
│                                                              │
└────────────────┬───────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
    ✓ OK                ✗ EXCEEDED
    (create)           (reject / enqueue)
        │                 │
        ▼                 ▼
┌────────────────────┐  ┌──────────────────────┐
│ tmux new-window    │  │ Add to waiting queue  │
│ or split-window    │  │ (task-manager-sqlite)│
│                    │  │ status: 'pending'    │
│ Send message       │  │ (retry after pane    │
│ (task instructions)│  │  becomes available)  │
└────────────────────┘  └──────────────────────┘
```

### 5-3. Concurrency Check (Python 実装例)

```python
def validate_concurrency_limit(
    session_name: str,
    window_name: str,
    role: str
) -> tuple[bool, str]:
    """
    Check if new pane creation would exceed concurrency limits.
    
    Returns:
        (is_allowed: bool, reason: str)
    """
    
    # Orchestrator: max 1 session, 1 pane
    if role == "orchestrator":
        # Already protected: only 1 ai-orchestrator@main:0:0 allowed
        # script should not try to create another
        sessions = tmux_list_sessions("^ai-orchestrator@main$")
        if len(sessions) > 0:
            return False, "orchestrator session already exists"
        panes = tmux_list_panes(f"{session_name}:0")
        if len(panes) > 0:
            return False, "orchestrator window:0 already has pane"
        return True, ""
    
    # Check role-specific limits
    if role in ["pm", "em"]:
        # managers window: max 2 panes
        panes = tmux_list_panes(f"{session_name}:managers")
        if len(panes) >= 2:
            return False, f"managers window already has {len(panes)} panes (max 2)"
        return True, ""
    
    if role == "engineer":
        # members window: max 3 panes
        panes = tmux_list_panes(f"{session_name}:members")
        if len(panes) >= 3:
            return False, f"members window already has {len(panes)} panes (max 3)"
        return True, ""
    
    return False, f"unknown role: {role}"
```

---

## 6. エラーハンドリング・リカバリーフロー

### 6-1. エラー分類・対応マトリクス

| エラータイプ | 発生箇所 | 検出方法 | 対応 | リカバリー |
|------------|--------|--------|------|-----------|
| **Task Dependencies Cycle** | workflow generation | DAG validation | fail workflow | manual fix template |
| **Specialist Not Found** | assignment validation | specialist lookup | fail workflow | assign available specialist |
| **Pane Unresponsive** | engineer execution | no output > 10min | escalate & log | kill & restart pane |
| **Task Status Stuck** | task execution | task.py show (no update > deadline) | escalate & log | re-assign engineer |
| **Database Transaction Fail** | workflow instance creation | SQLite error | rollback & retry | retry with exponential backoff |
| **tmux Session Not Found** | orchestrator scan | capture-pane error | log & ignore | recreate session |
| **GitHub API Rate Limit** | engineer git push | git error | throttle & retry | exponential backoff + queue |
| **Concurrency Limit Exceeded** | pane creation | validate_concurrency_limit | enqueue task | poll available pane |

### 6-2. エラーハンドリングフロー図

```
┌─────────────────────────────────────────────────────┐
│           Error Detection (multiple sources)        │
│                                                     │
│ - pane_status.py (orchestrator loop)               │
│ - health_check.py (periodic health check)          │
│ - exception handling (in ccc sessions)             │
│ - webhook (from task-manager-sqlite)               │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
    [Automatic]       [Manual]
    (auto-recovery)   (escalation)
        │                 │
        ▼                 ▼
┌──────────────────────────────────────────────────────┐
│     Error Severity Classification                   │
│                                                     │
│ CRITICAL:  System halt risk                        │
│   → immediate escalation to user                   │
│                                                     │
│ WARNING:   Task execution delayed                  │
│   → attempt auto-recovery, then escalate if fail   │
│                                                     │
│ INFO:      Normal operational condition            │
│   → log, monitor, no action needed                 │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────┴─────────────┬────────────┐
        │                      │            │
    [CRITICAL]         [WARNING]       [INFO]
        │                  │              │
        ▼                  ▼              ▼
┌──────────────────────────────────────────────────────┐
│              Recovery Strategy                       │
│                                                     │
│ 1. Log error (alert_aggregator.py)                │
│ 2. Determine recovery action:                      │
│    - Auto-repair (if in CLAUDE.md)                │
│    - Retry (exponential backoff)                  │
│    - Escalation (to user / Discord)              │
│ 3. Implement recovery                             │
│ 4. Verify success                                 │
│ 5. If fail, escalate                              │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────┴──────────┐
        │                   │
     [Success]         [Failed]
        │                   │
        ▼                   ▼
┌─────────────────┐  ┌──────────────────────┐
│ Resume workflow │  │ Create incident task │
│ Log recovery    │  │ Escalate to user     │
│ Continue loop   │  │ Manual intervention  │
└─────────────────┘  └──────────────────────┘
```

### 6-3. 具体的な Recovery Scripts

#### Recovery 1: Pane Unresponsive Handling

```python
def handle_unresponsive_pane(session: str, window: str, pane: int):
    """
    Handle pane with no output for > 10 minutes.
    
    Steps:
    1. Confirm unresponsive (verify timestamp)
    2. Check for errors in pane
    3. Try to recover:
       a. Send Ctrl+C (interrupt)
       b. Wait 5 seconds
       c. Check response
       d. If still no response, kill pane
    4. If critical role, restart immediately
    5. Log incident
    """
    
    pane_id = f"{session}:{window}.{pane}"
    
    # Confirm unresponsiveness
    output = tmux_capture_pane(pane_id)
    if len(output.strip()) == 0:
        log_warning(f"Pane {pane_id} appears unresponsive (no output)")
    
    # Try interrupt
    tmux_send_keys(pane_id, "C-c")
    time.sleep(5)
    
    # Recheck
    output_after = tmux_capture_pane(pane_id)
    if len(output_after.strip()) > len(output.strip()):
        log_info(f"Pane {pane_id} recovered after interrupt")
        return
    
    # Kill and recreate if critical
    role = determine_role_from_window(window)
    if role in ["em", "orchestrator"]:
        log_critical(f"Killing critical pane {pane_id}")
        escalate_to_user(f"pane {pane_id} unresponsive, action required")
        # Do NOT auto-restart (requires user decision)
    else:
        # Engineer pane: safe to kill
        tmux_kill_pane(pane_id)
        log_info(f"Killed pane {pane_id}, reassigning task")
        # Reassign task to next available engineer
        reassign_task(get_pane_task_id(pane_id))
```

#### Recovery 2: Task Status Stuck (Deadline Exceeded)

```python
def handle_task_stuck(task_id: int, deadline: datetime):
    """
    Handle task not updated within deadline.
    
    Steps:
    1. Confirm task not updated
    2. Find assigned engineer
    3. Check engineer pane status
    4. If pane responsive:
       a. Send reminder message
       b. Set new deadline (24h from now)
    5. If pane unresponsive:
       a. Treat as pane error
       b. Reassign task
    6. Log incident
    """
    
    task = task_manager.get_task(task_id)
    if task.status == "completed":
        return  # Already done
    
    now = datetime.now()
    if now < deadline:
        return  # Not yet deadline
    
    # Task is stuck
    engineer_id = task.assigned_to
    engineer_session = find_engineer_session(engineer_id)
    
    if not engineer_session:
        log_warning(f"Task {task_id} engineer session not found")
        escalate_to_user(f"Task {task_id} stuck, engineer offline")
        return
    
    pane_output = tmux_capture_pane(engineer_session)
    if is_responsive(pane_output):
        # Send reminder
        tmux_send_keys(engineer_session, 
            f"# Reminder: Task #{task_id} deadline exceeded")
        task_manager.update_task(task_id, deadline=now + timedelta(hours=24))
        log_warning(f"Task {task_id} reminder sent")
    else:
        # Pane unresponsive
        handle_unresponsive_pane(*engineer_session)
```

---

## 7. 監視・ヘルスチェック・異常検知

### 7-1. 監視エコシステム

```
┌────────────────────────────────────────────────────────────────┐
│                  Orchestrator Monitoring Loop                  │
│                     (every 3 minutes)                          │
│                                                                │
│  /loop 3m /orchestrate                                        │
│   ├─ scan all panes (detect input wait)                      │
│   ├─ health_check.py → metrics                               │
│   │  ├─ response_time metrics                                │
│   │  ├─ error rate metrics                                   │
│   │  ├─ resource utilization                                 │
│   │  └─ database health                                      │
│   ├─ cycle_stats_writer.py → SQLite log                      │
│   │  ├─ timestamp                                            │
│   │  ├─ pane count by role                                   │
│   │  ├─ task progress                                        │
│   │  └─ errors detected                                      │
│   ├─ alert_aggregator.py → review alerts                     │
│   │  ├─ escalate critical                                    │
│   │  ├─ log warnings                                         │
│   │  └─ auto-recovery triggers                              │
│   ├─ detect pending tasks                                    │
│   │  └─ start_pane.py → new team session                    │
│   └─ report dashboard                                        │
│      └─ http://localhost:8503 (Streamlit)                   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 7-2. Health Check Metrics

```python
class HealthMetrics:
    """
    Comprehensive health check metrics for orchestrator monitoring.
    """
    
    # Infrastructure
    tmux_sessions_count: int  # total active sessions
    tmux_windows_count: int   # total windows across sessions
    tmux_panes_count: int     # total panes
    
    # Concurrency Compliance
    orchestrator_session_count: int  # should be 1
    orchestrator_panes_in_0: int     # should be 1
    team_sessions_count: int         # any number
    managers_panes_max: int          # per window, should be ≤ 2
    members_panes_max: int           # per window, should be ≤ 3
    
    # Performance
    avg_pane_response_time_ms: float
    max_pane_response_time_ms: float
    
    # Errors
    error_count_last_cycle: int
    critical_error_count: int
    pane_unresponsive_count: int
    
    # Tasks
    pending_task_count: int
    in_progress_task_count: int
    completed_task_count_last_24h: int
    avg_task_turnaround_time_hours: float
    
    # Database
    database_size_mb: float
    last_vacuum_time: datetime
    connection_latency_ms: float
    
    # Timestamp
    check_timestamp: datetime
    check_duration_ms: float
```

### 7-3. Alert Rules

```yaml
# alert_rules.yaml
alerts:
  
  - name: "Orchestrator Session Missing"
    condition: "orchestrator_session_count != 1"
    severity: "CRITICAL"
    action: "escalate_to_user"
    message: "Orchestrator session not found, restart required"
  
  - name: "Orchestrator Window:0 Corrupted"
    condition: "orchestrator_panes_in_0 != 1"
    severity: "CRITICAL"
    action: "escalate_to_user"
    message: "Orchestrator window:0 has {orchestrator_panes_in_0} panes (expected 1)"
  
  - name: "Managers Window Overloaded"
    condition: "managers_panes_max > 2"
    severity: "WARNING"
    action: "log_warning + escalate"
    message: "Managers window has {managers_panes_max} panes (max 2)"
  
  - name: "Members Window Overloaded"
    condition: "members_panes_max > 3"
    severity: "WARNING"
    action: "kill_excessive_pane + log"
    message: "Members window has {members_panes_max} panes (max 3), killing pane {pane_id}"
  
  - name: "Pane Unresponsive"
    condition: "pane_last_output_age_min > 10"
    severity: "WARNING"
    action: "auto_recovery (attempt interrupt, then kill if critical)"
    message: "Pane {pane_id} has no output for {pane_last_output_age_min} minutes"
  
  - name: "High Error Rate"
    condition: "error_count_last_cycle > 5"
    severity: "WARNING"
    action: "log_warning + escalate"
    message: "High error count: {error_count_last_cycle} errors in last cycle"
  
  - name: "Task Stuck (Deadline)"
    condition: "task.status == 'in_progress' AND now > task.deadline"
    severity: "WARNING"
    action: "send_reminder + extend_deadline"
    message: "Task #{task_id} deadline exceeded, reminder sent"
  
  - name: "Database Growing (>100MB)"
    condition: "database_size_mb > 100"
    severity: "INFO"
    action: "log_info + suggest_vacuum"
    message: "Database size: {database_size_mb}MB, consider vacuum"
```

### 7-4. Dashboard (Streamlit)

```python
# dashboard.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def main():
    st.title("AI Orchestrator Health Dashboard")
    
    # Sidebar: time range selector
    time_range = st.sidebar.selectbox(
        "Time Range",
        ["Last 1 Hour", "Last 24 Hours", "Last 7 Days"]
    )
    
    # Tab 1: System Status
    with st.container():
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Sessions", orchestrator.session_count)
        with col2:
            st.metric("Active Panes", orchestrator.pane_count)
        with col3:
            st.metric("Pending Tasks", task_manager.pending_count)
    
    # Tab 2: Concurrency Monitor
    st.subheader("Concurrency Limits")
    concurrency_data = {
        "Role": ["orchestrator", "managers", "members"],
        "Current": [
            orchestrator.session_count,
            max([len(tmux_list_panes(f"{s}:managers")) 
                 for s in orchestrator.team_sessions]),
            max([len(tmux_list_panes(f"{s}:members")) 
                 for s in orchestrator.team_sessions]),
        ],
        "Limit": [1, 2, 3],
        "Status": ["OK", "OK", "OK"]  # colored
    }
    st.dataframe(pd.DataFrame(concurrency_data))
    
    # Tab 3: Recent Errors
    st.subheader("Recent Errors")
    errors = alert_aggregator.get_recent_alerts(limit=10)
    st.dataframe(errors)
    
    # Tab 4: Task Progress
    st.subheader("Task Progress (Last 24h)")
    task_stats = task_manager.get_stats(timedelta(hours=24))
    st.bar_chart(task_stats)
    
    # Auto-refresh
    st.rerun_every(60)  # refresh every 60 seconds

if __name__ == "__main__":
    main()
```

---

## 8. 実装チェックリスト

### Phase 1: Core Infrastructure (✓ 実装済み)
- [x] tmux session / window / pane management
- [x] SQLite workflow template schema
- [x] task-manager-sqlite integration
- [x] start_pane.py (pane creation script)
- [x] CLAUDE.md (orchestrator instructions)

### Phase 2: Orchestrator Loop (✓ 実装済み)
- [x] `/loop 3m /orchestrate` command
- [x] pane_status.py (tmux scan)
- [x] health_check.py (metrics)
- [x] alert_aggregator.py (error handling)
- [x] cycle_stats_writer.py (logging)

### Phase 3: Workflow Template System (✓ 実装済み)
- [x] workflow_templates table
- [x] wf_template_phases table
- [x] wf_template_tasks table
- [x] WorkflowService (core logic)
- [x] advance_wf_instance.py (workflow execution)

### Phase 4: Data Generation & Dependencies (✓ 実装済み)
- [x] TaskGenerationService
- [x] DependencyResolver (DAG)
- [x] dev_tasks table (auto-generated)
- [x] task_dependencies (graph DB)

### Phase 5: Concurrency Limit Enforcement (✓ Partial)
- [x] Rule definition (CLAUDE.md)
- [ ] validate_concurrency_limit() function
- [ ] start_pane.py integration
- [ ] Dashboard visualization
- [ ] Automated enforcement (kill excessive panes)

### Phase 6: Error Handling & Recovery (⚠️ In Progress)
- [x] alert_aggregator.py (error classification)
- [x] auto_recovery.py (basic recovery logic)
- [x] discord_notifier.py (escalation)
- [ ] Comprehensive recovery flows (documented)
- [ ] Recovery strategy matrix (per error type)

### Phase 7: Monitoring & Observability (⚠️ Partial)
- [x] health_check.py (metrics)
- [x] cycle_stats_writer.py (logging)
- [x] alert_rules.yaml (alert definitions)
- [x] dashboard (Streamlit)
- [ ] Real-time dashboard updates
- [ ] SLA monitoring (task deadline tracking)

### Phase 8: Integration Testing (Pending)
- [ ] End-to-end workflow test
- [ ] Concurrency limit test
- [ ] Error recovery test
- [ ] Dashboard functionality test
- [ ] Performance load test

---

## Document References

- **Architecture**: [architecture-design.md](architecture-design.md)
- **Data Model**: [data-model.md](data-model.md)
- **Flow Design**: [flow-design.md](flow-design.md)
- **Workflow Template**: [workflow-template-design.md](workflow-template-design.md)
- **Orchestrator Instructions**: [../CLAUDE.md](../CLAUDE.md)
- **Scan Protocol**: [../ref/scan.md](../ref/scan.md)
- **Recovery Protocol**: [../ref/recovery.md](../ref/recovery.md)

---

## History

| Date | Version | Changes |
|------|---------|---------|
| 2026-04-19 | v1.0 | Initial BDD design document |

