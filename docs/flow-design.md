# ワークフローテンプレートシステム - 処理フロー設計

**作成日**: 2026-04-18  
**バージョン**: v1.0 (Phase 3)  
**対応**: architecture-design.md, data-model.md の実装パターン

---

## 目次

1. [テンプレート→インスタンス化フロー](#1-テンプレートインスタンス化フロー)
2. [フェーズ実行状態遷移](#2-フェーズ実行状態遷移)
3. [タスク自動生成フロー](#3-タスク自動生成フロー)
4. [依存関係解決アルゴリズム](#4-依存関係解決アルゴリズム)
5. [Specialist アサイン検証フロー](#5-specialist-アサイン検証フロー)

---

## 1. テンプレート→インスタンス化フロー

### 1-1. 全体シーケンス（5段階）

```
┌──────────────────────────────────────────────────────────────────────┐
│ Input: template_id, specialist_assignments, workflow_name            │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                    Step 1: Validate
                              │
                    ┌─────────▼──────────┐
                    │ Template Exists?   │
                    │ Specialist Valid?  │
                    │ Phase Count OK?    │
                    └─────────┬──────────┘
                              │ ✓ OK
                              │
                    ┌─────────▼──────────────────┐
              Step 2: Create Instance Record     │
              ┌─────────────────────────────────┘
              │
        ┌─────▼──────────────────────────┐
        │ workflow_instances insert      │
        │ - id (auto-inc)                │
        │ - template_id                  │
        │ - name                         │
        │ - status = 'pending'           │
        │ - context = {}                 │
        │ - created_at = now()           │
        └──────────┬──────────────────────┘
                   │
      Step 3: Assign Specialists
                   │
        ┌──────────▼──────────────────────┐
        │ workflow_instance_specialists   │
        │ insert for each phase:          │
        │ - instance_id                   │
        │ - phase_id                      │
        │ - specialist_id                 │
        │ - specialist_slug               │
        │ - specialist_name               │
        └──────────┬──────────────────────┘
                   │
    Step 4: Create Phase Instances
                   │
        ┌──────────▼──────────────────────┐
        │ wf_instance_nodes insert        │
        │ For each phase:                 │
        │ - instance_id                   │
        │ - node_key = phase_key          │
        │ - node_type = 'phase'           │
        │ - status = 'waiting'            │
        │ (later: task_id after gen)      │
        └──────────┬──────────────────────┘
                   │
    Step 5: Generate Tasks
                   │
        ┌──────────▼──────────────────────┐
        │ generate_tasks_for_instance()   │
        │ (see Section 3 for details)     │
        └──────────┬──────────────────────┘
                   │
                   ▼
        Instance Ready: status = 'ready'
          All tasks created, dependencies set
```

### 1-2. データフロー

```
Template Layer                Instance Layer                Task Layer
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│ workflow_    │  read    │ workflow_    │  create  │  dev_tasks   │
│ templates    │─────────►│ instances    │─────────►│  (phase=pk)  │
│              │          │              │          │              │
└──────────────┘          └──────┬───────┘          └──────────────┘
       │                          │                        △
       │ read                      │ write                  │ insert
       ▼                          ▼                        │
┌──────────────────┐    ┌──────────────────────┐         │
│ wf_template_     │    │ workflow_instance_   │         │
│ phases           │    │ specialists          │────────┘
│ (phase_order)    │    │ (phase → specialist) │
└─────────┬────────┘    └──────────────────────┘
          │
          │ read
          ▼
┌──────────────────┐
│ wf_template_     │
│ tasks            │
│ (task_defs)      │
└──────────────────┘

KuzuDB Graph:
   task_dependencies edges
   + inter-phase deps (phase N+1 blocks on phase N)
   + intra-phase deps (depends_on_key resolution)
```

### 1-3. エラーハンドリング

| エラー | 原因 | 対応 |
|--------|------|------|
| TemplateNotFoundError | template_id が存在しない | 即座に fail、rollback |
| ValidationError | specialist_assignments が不正 | エラーメッセージ返却 |
| SpecialistAssignmentError | specialist が見つからない | エラーメッセージ返却 |
| CircularDependencyError | depends_on_key の循環 | 設計時エラー、テンプレート再確認 |
| DatabaseError | transaction 失敗 | rollback、リトライ推奨 |

---

## 2. フェーズ実行状態遷移

### 2-1. Phase 状態マシン

```
                    ┌──────────┐
                    │ waiting  │◄──── Phase N-1 未完了
                    └─────┬────┘
                          │
                          │ Phase N-1 完了 & task_dependencies.unblock_successors()
                          │
                    ┌─────▼────┐
                    │ ready    │◄──── Phase 内のすべてのタスク created
                    └─────┬────┘
                          │
                          │任意の specialist が first task を開始
                          │ Status update: dev_tasks.status → 'in_progress'
                          │
                    ┌─────▼────┐
                    │ running  │◄──── Specialist による作業継続
                    └─────┬────┘
                          │
                          │ Phase 内のすべてのタスク completed
                          │ status check: all tasks.status == 'completed'
                          │
                    ┌─────▼────┐
                    │ completed│◄──── unblock_successors() → Phase N+1 ready
                    └──────────┘
```

### 2-2. 状態遷移トリガーと条件

| 遷移 | トリガー | 条件チェック | 結果 |
|-----|---------|-----------|------|
| waiting → ready | Phase N-1 completed | task_dependencies.unblock_successors() で Phase N の全タスク unblock | Phase N の全タスク pending に遷移 |
| ready → running | 任意タスク started | dev_tasks.status='in_progress' | Phase instance status = running に更新 |
| running → completed | 全タスク completed | COUNT(status='completed') == phase.task_count | Phase N+1 への unblock 実行 |

### 2-3. wf_instance_nodes でのステータス管理

```python
# Phase Instance Node (wf_instance_nodes)
class PhaseInstanceNode:
    id: int
    instance_id: int         # workflow_instances.id
    template_node_id: int    # wf_template_nodes.id (if exists)
    node_key: str            # phase_key (e.g., 'planning', 'development')
    node_type: str = 'phase' # fixed
    status: str              # waiting, ready, running, completed
    result: str | None       # 分岐判定用（current: always None）
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
```

**Status Update Logic:**

```
Instance Creation:
  wf_instance_nodes.insert(status='waiting')

Phase N-1 Completed:
  UPDATE wf_instance_nodes
  SET status='ready'
  WHERE node_key IN (select phase_key from wf_template_phases where phase_order = N)
  
  -- Also unblock associated dev_tasks
  UPDATE dev_tasks
  SET status='pending', unblocked_at=now()
  WHERE phase='phase_N' AND status='blocked'

First Task in Phase Started:
  UPDATE wf_instance_nodes
  SET status='running', started_at=now()
  WHERE node_key='phase_N'

Phase Completed:
  UPDATE wf_instance_nodes
  SET status='completed', completed_at=now()
  WHERE node_key='phase_N'
  
  -- Then trigger Phase N+1 unblock
  CALL task_dependencies.unblock_successors(...)
```

---

## 3. タスク自動生成フロー

### 3-1. 生成アルゴリズム（疑似コード）

```python
def generate_tasks_for_instance(instance_id: int) -> int:
    """
    インスタンス → dev_tasks 全体生成
    Returns: 生成タスク数
    """
    instance = workflow_instances.get(instance_id)
    template = workflow_templates.get(instance.template_id)
    
    # Phase を phase_order でソート
    phases = wf_template_phases.get_all(
        template_id=template.id,
        order_by='phase_order'
    )
    
    total_generated = 0
    prev_phase_tasks = []  # フェーズ間依存の設定用
    
    for phase in phases:
        # フェーズに割り当てられた specialist を取得
        specialist = workflow_instance_specialists.get(
            instance_id=instance_id,
            phase_id=phase.id
        )
        
        # Phase 内のタスク定義を取得
        task_defs = wf_template_tasks.get_all(
            phase_id=phase.id,
            order_by='task_order'  # Define task_order in template
        )
        
        phase_tasks = []
        
        for task_def in task_defs:
            # プレースホルダ置換
            title = apply_placeholders(
                task_def.task_title,
                phase=phase.phase_label,
                specialist_name=specialist.specialist_name
            )
            description = apply_placeholders(
                task_def.task_description,
                phase=phase.phase_label,
                specialist_name=specialist.specialist_name
            )
            
            # Task 作成（初期状態: blocked）
            task = dev_tasks.insert(
                title=title,
                description=description,
                assignee=specialist.specialist_slug,
                phase=phase.phase_key,
                workflow_instance_id=instance_id,
                wf_node_key=phase.phase_key,
                status='blocked',  # Phase N-1 完了まで blocked
                priority=task_def.priority,
                estimated_hours=task_def.estimated_hours
            )
            phase_tasks.append(task)
            total_generated += 1
        
        # フェーズ内タスク依存関係を設定
        for task in phase_tasks:
            task_def = wf_template_tasks.get(task.id)
            if task_def.depends_on_key:
                # 同一フェーズ内の先行タスク（key: depends_on_key）を探す
                predecessor_def = wf_template_tasks.get_by_key(
                    phase_id=phase.id,
                    task_key=task_def.depends_on_key
                )
                predecessor_task = [
                    t for t in phase_tasks
                    if t.wf_template_task_id == predecessor_def.id
                ][0]
                
                # task_dependencies に記録
                task_dependencies.insert(
                    predecessor_id=predecessor_task.id,
                    successor_id=task.id,
                    dep_type='intra_phase'
                )
        
        # フェーズ間依存関係を設定（Phase N-1 → Phase N）
        if prev_phase_tasks:
            # Phase N-1 のすべてのタスク完了で Phase N の全タスク unblock
            for prev_task in prev_phase_tasks:
                for curr_task in phase_tasks:
                    task_dependencies.insert(
                        predecessor_id=prev_task.id,
                        successor_id=curr_task.id,
                        dep_type='inter_phase'
                    )
        
        prev_phase_tasks = phase_tasks
    
    return total_generated
```

### 3-2. Placeholder 置換ルール

```python
def apply_placeholders(template_text: str, **context) -> str:
    """
    Template: "Design {phase_label} with {specialist_name}"
    Context: phase_label='Planning', specialist_name='Alice'
    Result:  "Design Planning with Alice"
    """
    result = template_text
    
    # 定義済み placeholder
    placeholders = {
        '{phase_label}': context.get('phase', ''),
        '{phase_key}': context.get('phase', ''),
        '{specialist_name}': context.get('specialist_name', ''),
        '{specialist_slug}': context.get('specialist_slug', ''),
        '{specialist_email}': context.get('specialist_email', ''),
        '{workflow_name}': context.get('workflow_name', ''),
        '{current_date}': datetime.now().isoformat(),
    }
    
    for placeholder, value in placeholders.items():
        result = result.replace(placeholder, value)
    
    # 未置換の placeholder は warning log し、そのままにする
    import re
    unresolved = re.findall(r'\{[^}]+\}', result)
    if unresolved:
        logger.warning(f"Unresolved placeholders: {unresolved}")
    
    return result
```

### 3-3. Idempotency 保証

```python
def generate_tasks_for_instance(instance_id: int) -> int:
    """
    複数回呼び出しても同じ結果を保証
    """
    instance = workflow_instances.get(instance_id)
    
    # 既に生成済みかチェック
    existing_count = dev_tasks.count(
        workflow_instance_id=instance_id
    )
    if existing_count > 0:
        logger.info(f"Tasks already generated for instance {instance_id}")
        return existing_count  # 再生成しない
    
    # 生成処理
    ...
```

---

## 4. 依存関係解決アルゴリズム

### 4-1. レベル 1: フェーズ間依存（Phase-to-Phase）

```
Phase 0 (Planning)
├─ Task 0.1 ──┐
├─ Task 0.2 ──┤
└─ Task 0.3 ──┤
              │ All completed
              ▼
Phase 1 (Development)    ◄── unblock_successors() → status: blocked → pending
├─ Task 1.1
├─ Task 1.2
└─ Task 1.3
```

**実装:**

```python
# task_dependencies table:
# predecessor_id | successor_id | dep_type
# Task 0.1       | Task 1.1     | inter_phase
# Task 0.1       | Task 1.2     | inter_phase
# Task 0.1       | Task 1.3     | inter_phase
# Task 0.2       | Task 1.1     | inter_phase
# ...

def unblock_successors(predecessor_id: int) -> int:
    """
    先行タスク完了時にコール
    Returns: unblock されたタスク数
    """
    successors = task_dependencies.get_successors(
        predecessor_id=predecessor_id
    )
    
    unblocked = 0
    for successor in successors:
        # successors の全 predecessors が completed か確認
        blocking_preds = task_dependencies.get_predecessors(
            successor_id=successor.id,
            status_not_in=['completed']
        )
        
        if not blocking_preds:  # All predecessors completed
            dev_tasks.update(
                id=successor.id,
                status='pending',
                unblocked_at=now()
            )
            unblocked += 1
    
    return unblocked
```

### 4-2. レベル 2: フェーズ内依存（Intra-Phase）

```
Task 1.1 (Architecture Design)
  │
  │ depends_on_key='design-arch'
  ▼
Task 1.2 (Implement Based on Design)
  │
  │ depends_on_key='implement'
  ▼
Task 1.3 (Test Implementation)
```

**実装:**

```python
# wf_template_tasks:
# id | phase_id | task_key  | depends_on_key | task_title
# 15 | 2        | arch      | NULL           | Architecture Design
# 16 | 2        | impl      | arch           | Implement Features
# 17 | 2        | test      | impl           | Testing

# During task generation:
for task_def in phase_task_defs:
    if task_def.depends_on_key:
        pred_def = wf_template_tasks.get_by_key(
            phase_id=phase.id,
            task_key=task_def.depends_on_key
        )
        task_dependencies.insert(
            predecessor_id=corresponding_task_of(pred_def),
            successor_id=new_task.id,
            dep_type='intra_phase'
        )
```

### 4-3. 循環依存検出

```python
def validate_dependencies_dag() -> bool:
    """
    template 保存時に循環検出
    KuzuDB グラフDB を活用
    """
    # KuzuDB に全 edge を read
    graph = kuzu_db.get_dependency_graph(template_id)
    
    # DFS で循環検出
    if graph.has_cycle():
        raise CircularDependencyError(
            f"Circular dependency found: {graph.get_cycle_path()}"
        )
    
    return True
```

---

## 5. Specialist アサイン検証フロー

### 5-1. 入力から DB 記録までのフロー

```
┌─────────────────────────────────────────────────────┐
│ Input: specialist_assignments dict                 │
│ {                                                  │
│   "planning": "alice@example.com",                │
│   "development": 5,  (agent_id)                   │
│   "testing": "carol@example.com"                  │
│ }                                                  │
└────────────────┬────────────────────────────────────┘
                 │
        Step 1: Validate Format
                 │
        ┌────────▼──────────────┐
        │ Each phase has entry? │
        │ Values are valid?     │
        │ (email or agent_id)   │
        └────────┬───────────────┘
                 │ ✓
        ┌────────▼──────────────────────┐
 Step 2: Resolve Identifiers             │
 ┌────────────────────────────────────────┘
 │
 ├─ If email: agents.get_by_email()
 ├─ If agent_id: agents.get(id)
 │
 └──────┬──────────────────────────────┐
        │ ✓ All found                  │
        │                               │
 ┌──────▼──────────────────────────────┐
 │ Step 3: Verify Agent Capabilities    │
 │ ├─ Check agent.specialist_type      │
 │ ├─ Matches phase.specialist_type?   │
 └──────┬──────────────────────────────┘
        │ ✓ OK
        │
 ┌──────▼──────────────────────────────────┐
 │ Step 4: Record in workflow_instance_    │
 │ specialists table                       │
 │ ├─ instance_id                         │
 │ ├─ phase_id                            │
 │ ├─ specialist_id (agent.id)            │
 │ ├─ specialist_slug (email or name)     │
 │ ├─ specialist_name (agent.name)        │
 └──────┬──────────────────────────────────┘
        │
        ▼
    Assignment Complete
```

### 5-2. エラーケース

| エラー | 検出 | 対応 |
|--------|------|------|
| Phase に specialist 未割り当て | Step 1 | ValidationError: "Missing specialist for phase X" |
| Agent not found (email/ID 無効) | Step 2 | SpecialistNotFoundError: "Agent not found: alice@..." |
| Type mismatch (e.g., PM を QA phase へ) | Step 3 | SpecialistAssignmentError: "Agent type PM ≠ phase type QA" |
| DB constraint violation | Step 4 | DatabaseError + rollback |

### 5-3. Specialist Validation Service

```python
class SpecialistAssignmentService:
    def validate_assignments(
        self,
        template_id: int,
        assignments: dict[str, str|int]  # phase_key → email/agent_id
    ) -> dict[str, Agent]:
        """
        Validate and resolve all specialist assignments
        Returns: { phase_key → Agent object }
        
        Raises:
        - ValidationError
        - SpecialistNotFoundError
        - SpecialistAssignmentError
        """
        template = template_repo.get(template_id)
        phases = template_repo.get_phases(template_id)
        
        # Step 1: Check all phases have assignment
        for phase in phases:
            if phase.phase_key not in assignments:
                raise ValidationError(
                    f"No specialist assigned to phase: {phase.phase_key}"
                )
        
        resolved = {}
        
        # Step 2-3: Resolve & validate
        for phase in phases:
            identifier = assignments[phase.phase_key]
            
            # Try email first, then agent_id
            agent = None
            if '@' in str(identifier):
                agent = specialist_repo.get_by_email(identifier)
            else:
                agent = specialist_repo.get(identifier)
            
            if not agent:
                raise SpecialistNotFoundError(
                    f"Agent not found: {identifier}"
                )
            
            # Type check (optional: depends on business rule)
            if agent.specialist_type != phase.specialist_type:
                logger.warning(
                    f"Type mismatch: agent type {agent.specialist_type} "
                    f"≠ phase type {phase.specialist_type}"
                )
            
            resolved[phase.phase_key] = agent
        
        return resolved
```

---

## 6. 統合フロー例：「Product Launch」テンプレート

### 6-1. 入力

```json
{
  "template_id": 1,
  "workflow_name": "Product Launch #1",
  "specialist_assignments": {
    "planning": "alice@example.com",
    "development": "bob@example.com",
    "testing": "carol@example.com",
    "deployment": 7  // agent_id
  }
}
```

### 6-2. 実行ステップ

```
1. Validate template + assignments
   ✓ Template exists
   ✓ 4 phases defined
   ✓ All specialists assigned & valid

2. Create workflow_instances
   ✓ INSERT instance (id=42)

3. Assign specialists
   ✓ INSERT workflow_instance_specialists (4 rows)
     - planning → alice (id=1)
     - development → bob (id=2)
     - testing → carol (id=3)
     - deployment → dave (id=7)

4. Create phase instances
   ✓ INSERT wf_instance_nodes (4 rows, all status='waiting')

5. Generate tasks
   ✓ INSERT dev_tasks (3+5+4+2=14 rows, all status='blocked')
   ✓ INSERT task_dependencies (intra_phase + inter_phase edges)
   ✓ KuzuDB: cycle check passed

6. Instance Ready
   ✓ workflow_instances.status = 'ready'
   ✓ Return instance_id=42
```

### 6-3. タスク生成結果

```
Phase 0: Planning (alice) - status: waiting
├─ Task 0.1: Design product strategy
├─ Task 0.2: Create requirements document
└─ Task 0.3: Prepare launch timeline

Phase 1: Development (bob) - status: waiting (blocked on Phase 0)
├─ Task 1.1: Architecture design
├─ Task 1.2: Implement backend API
├─ Task 1.3: Implement frontend UI
├─ Task 1.4: Integration testing (depends_on_key: impl)
└─ Task 1.5: Code review

Phase 2: Testing (carol) - status: waiting (blocked on Phase 1)
├─ Task 2.1: Prepare test plan
├─ Task 2.2: Execute system tests
├─ Task 2.3: Load testing
└─ Task 2.4: Security audit

Phase 3: Deployment (dave) - status: waiting (blocked on Phase 2)
├─ Task 3.1: Prepare deployment guide
└─ Task 3.2: Execute deployment
```

---

## 7. トレーサビリティ

### 7-1. 監査ログ

各操作で以下を記録（future enhancement）:

```sql
-- audit_logs table (future)
CREATE TABLE audit_logs (
  id INTEGER PRIMARY KEY,
  entity_type TEXT,        -- 'workflow_template', 'workflow_instance', 'dev_task'
  entity_id INTEGER,
  action TEXT,             -- 'create', 'instantiate', 'task_generate', 'status_change'
  actor_id INTEGER,        -- who performed
  old_value JSON,
  new_value JSON,
  timestamp DATETIME
);
```

### 7-2. タスク ID マッピング

```
Template Task → Instance Task の追跡:

wf_template_tasks.id=15
  ↓ (during generation)
dev_tasks.id=201 (wf_template_task_id=15)
dev_tasks.workflow_instance_id=42
dev_tasks.phase='development'

dev_tasks.id=201 is linked to:
├─ wf_instance_nodes (via wf_node_key='development')
├─ task_dependencies (as predecessor/successor)
└─ workflow_instance_specialists (via phase lookup)
```

---

## まとめ

このフロー設計により以下を実現：

✅ **テンプレートの再利用性**: 同じテンプレートから複数インスタンス生成可能  
✅ **柔軟な Specialist 割り当て**: インスタンスごとに異なる specialist 組み合わせ対応  
✅ **自動タスク生成**: フェーズ・依存関係・プレースホルダを自動解決  
✅ **Idempotency**: 同じ入力に対し常に同じ結果  
✅ **トレーサビリティ**: テンプレート → インスタンス → タスク → 実行 まで追跡可能  
✅ **エラーハンドリング**: 各段階での入力検証と循環検出  

---

## 参考資料

- **データモデル詳細**: `/docs/data-model.md`
- **アーキテクチャ**: `/docs/architecture-design.md`
- **設計背景**: `/docs/workflow-template-design.md`
- **BDD シナリオ**: `/features/workflow-template.feature`
