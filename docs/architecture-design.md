# ワークフローテンプレートシステム - システムアーキテクチャ設計

**作成日**: 2026-04-18  
**バージョン**: v1.0 (Phase 3)  
**対応**: data-model.md と相互参照

---

## 目次

1. [アーキテクチャ概要](#1-アーキテクチャ概要)
2. [レイヤー構成](#2-レイヤー構成)
3. [モジュール設計](#3-モジュール設計)
4. [インターフェース定義](#4-インターフェース定義)
5. [エラーハンドリング & 例外設計](#5-エラーハンドリング--例外設計)

---

## 1. アーキテクチャ概要

### 1-1. 全体図

```
┌──────────────────────────────────────────────────────────────────┐
│                     User / External Systems                       │
│                    (orchestrator / EM / API)                      │
└────────┬─────────────────────────────────────────────────────────┘
         │
         ├─── CLI Commands / REST API
         │
┌────────▼─────────────────────────────────────────────────────────┐
│                        Presentation Layer                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ CLI Interface (task.py --wf コマンド)                     │   │
│  │ ├─ wf template create / show / list                      │   │
│  │ ├─ wf instance start / show / status                     │   │
│  │ └─ wf instance node-done / timeline                      │   │
│  │                                                          │   │
│  │ REST API (future, Flask/FastAPI)                         │   │
│  │ └─ /api/workflow/template/{id}                           │   │
│  │ └─ /api/workflow/instance/{id}                           │   │
│  │ └─ /api/workflow/instance/{id}/task/{task_id}            │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────┬─────────────────────────────────────────────────────────┘
         │
┌────────▼─────────────────────────────────────────────────────────┐
│                    Application / Business Logic Layer              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ WorkflowService（ワークフロー管理）                        │   │
│  │ ├─ create_template()                                     │   │
│  │ ├─ instantiate_workflow()  ← 重要                        │   │
│  │ ├─ generate_tasks()        ← 重要                        │   │
│  │ ├─ advance_phase()                                       │   │
│  │ └─ get_instance_status()                                 │   │
│  │                                                          │   │
│  │ SpecialistAssignmentService（専門家割り当て）            │   │
│  │ ├─ assign_specialist()                                   │   │
│  │ ├─ validate_specialist()                                 │   │
│  │ └─ get_available_specialists()                           │   │
│  │                                                          │   │
│  │ TaskGenerationService（タスク生成）                       │   │
│  │ ├─ generate_tasks_for_phase()                            │   │
│  │ ├─ resolve_dependencies()                                │   │
│  │ └─ apply_placeholders()                                  │   │
│  │                                                          │   │
│  │ ValidationService（バリデーション）                       │   │
│  │ ├─ validate_template_schema()                            │   │
│  │ ├─ validate_phase_order()                                │   │
│  │ └─ validate_dependencies_dag()                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────┬─────────────────────────────────────────────────────────┘
         │
┌────────▼─────────────────────────────────────────────────────────┐
│                       Data Access Layer (DAL)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ SQLiteRepository（SQLite DB アクセス）                   │   │
│  │ ├─ TemplateRepository                                    │   │
│  │ │  ├─ create_template()                                  │   │
│  │ │  ├─ get_template()                                     │   │
│  │ │  ├─ get_phases()                                       │   │
│  │ │  └─ get_tasks()                                        │   │
│  │ ├─ InstanceRepository                                    │   │
│  │ │  ├─ create_instance()                                  │   │
│  │ │  ├─ get_instance()                                     │   │
│  │ │  └─ update_instance_status()                           │   │
│  │ ├─ SpecialistRepository                                  │   │
│  │ │  ├─ assign_specialist()                                │   │
│  │ │  └─ get_assigned_specialists()                         │   │
│  │ └─ TaskRepository                                        │   │
│  │    ├─ create_task()                                      │   │
│  │    ├─ create_dependency()                                │   │
│  │    └─ query_tasks()                                      │   │
│  │                                                          │   │
│  │ GraphRepository（KuzuDB グラフDB アクセス）              │   │
│  │ ├─ add_dependency_edge()                                 │   │
│  │ ├─ check_cycle()                                         │   │
│  │ ├─ get_unblocked_tasks()                                 │   │
│  │ └─ get_dependency_graph()                                │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────┬─────────────────────────────────────────────────────────┘
         │
┌────────▼─────────────────────────────────────────────────────────┐
│                     Infrastructure / Storage Layer                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ SQLite Database                                          │   │
│  │ ├─ workflow_templates, wf_template_phases, ...          │   │
│  │ ├─ workflow_instances, wf_instance_nodes, ...           │   │
│  │ ├─ dev_tasks, task_dependencies, ...                    │   │
│  │ └─ agents, teams, team_x_agents                         │   │
│  │                                                          │   │
│  │ KuzuDB Graph Database                                    │   │
│  │ ├─ Task dependency DAG                                   │   │
│  │ ├─ Agent ← → Task assignments                            │   │
│  │ └─ Workflow node transitions                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 1-2. アーキテクチャの原則

| 原則 | 説明 | メリット |
|-----|------|--------|
| **Layered Architecture** | プレゼンテーション/アプリケーション/DAL/インフラのレイヤー分離 | 各レイヤーの独立変更可能、テスト容易性 |
| **Repository Pattern** | DAL で SQLite・KuzuDB アクセスを抽象化 | DB 変更時の影響範囲最小化 |
| **Service Pattern** | ビジネスロジックを Service クラスに集約 | 再利用性、単体テスト容易性 |
| **Immutability（テンプレート層）** | template 作成後は読み取り専用 | バージョン管理、キャッシュ安全性 |
| **Idempotency（インスタンス化）** | 同じ入力には常に同じ結果 | リトライ安全性、分散実行対応 |

---

## 2. レイヤー構成

### 2-1. Presentation Layer（プレゼンテーション層）

#### 責務
- ユーザー入力の受け取り（CLI / REST API）
- 入力形式の初期バリデーション
- 結果の整形・出力

#### 主要コンポーネント

**CLI Interface (`task.py --wf` サブコマンド)**

```python
# コマンド群（既存 task.py に統合）
$ python3 task.py wf template create "Product Launch"
$ python3 task.py wf template add-phase 1 "planning" 1 "pm"
$ python3 task.py wf template add-task 1:planning "design-arch" "設計書作成"
$ python3 task.py wf instance start 1 "Product Launch #1" \
    --specialist-json '{"planning": 3, "development": 5}'
$ python3 task.py wf instance status 2
$ python3 task.py wf instance node-done 2 "planning"
```

**REST API Interface（将来実装、Flask/FastAPI）**

```python
# /api/workflow/template
POST   /api/workflow/template                 # テンプレート作成
GET    /api/workflow/template/{template_id}   # テンプレート取得
GET    /api/workflow/template                 # テンプレート一覧
PUT    /api/workflow/template/{template_id}   # 更新（draft のみ）

# /api/workflow/instance
POST   /api/workflow/instance                 # インスタンス作成
GET    /api/workflow/instance/{instance_id}   # インスタンス取得
GET    /api/workflow/instance                 # インスタンス一覧
PATCH  /api/workflow/instance/{instance_id}   # ステータス更新

# /api/workflow/instance/{instance_id}/node
POST   /api/workflow/instance/{instance_id}/node/{node_key}/done
GET    /api/workflow/instance/{instance_id}/timeline
```

### 2-2. Application / Business Logic Layer（アプリケーション層）

#### 責務
- ワークフロー管理ロジック（作成・インスタンス化・実行）
- 専門家割り当てロジック
- タスク自動生成ロジック
- バリデーション

#### 主要 Service クラス

##### `WorkflowService` - ワークフロー管理

```python
class WorkflowService:
    """ワークフロー全体を管理するサービス"""
    
    def __init__(self, template_repo, instance_repo, task_service):
        self.template_repo = template_repo
        self.instance_repo = instance_repo
        self.task_service = task_service
    
    def create_template(self, name: str, description: str) -> int:
        """テンプレートを作成して ID を返す"""
        return self.template_repo.create_template(name, description)
    
    def instantiate_workflow(self, template_id: int, instance_name: str,
                           specialist_assignments: dict) -> int:
        """
        テンプレート → インスタンスを生成
        
        Args:
            template_id: 対象テンプレート ID
            instance_name: インスタンス名（例: "Product Launch #1"）
            specialist_assignments: {phase_key → specialist_id} の dict
        
        Returns:
            新規作成した workflow_instances.id
        """
        # 1. バリデーション
        ValidationService.validate_specialist_assignments(
            template_id, specialist_assignments
        )
        
        # 2. インスタンス作成
        instance_id = self.instance_repo.create_instance(
            template_id, instance_name, specialist_assignments
        )
        
        # 3. タスク自動生成
        self.task_service.generate_tasks_for_instance(
            instance_id, template_id, specialist_assignments
        )
        
        return instance_id
    
    def advance_phase(self, instance_id: int, phase_key: str) -> None:
        """
        フェーズを waiting → ready → running → completed に進める
        """
        phase_node = self.instance_repo.get_phase_node(instance_id, phase_key)
        
        # 前フェーズ完了確認
        prev_phase = self.template_repo.get_prev_phase(
            phase_node.template_id, phase_node.phase_order
        )
        if prev_phase:
            prev_phase_node = self.instance_repo.get_phase_node(
                instance_id, prev_phase.phase_key
            )
            if prev_phase_node.status != 'completed':
                raise ValueError(f"Prev phase not completed: {prev_phase.phase_key}")
        
        # 遷移実行
        self.instance_repo.update_phase_status(phase_node.id, 'ready')
    
    def get_instance_status(self, instance_id: int) -> dict:
        """インスタンス全体の進行状況を取得"""
        instance = self.instance_repo.get_instance(instance_id)
        phases = self.instance_repo.get_phase_nodes(instance_id)
        tasks = self.task_service.get_tasks_for_instance(instance_id)
        
        return {
            'instance': instance,
            'phases': phases,
            'tasks': tasks,
            'overall_progress': self._calculate_progress(phases, tasks)
        }
    
    def _calculate_progress(self, phases, tasks) -> dict:
        """進行状況を計算"""
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t['status'] == 'completed')
        
        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'percentage': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        }
```

##### `SpecialistAssignmentService` - 専門家割り当て

```python
class SpecialistAssignmentService:
    """Specialist の割り当て・管理"""
    
    def __init__(self, specialist_repo, agent_repo):
        self.specialist_repo = specialist_repo
        self.agent_repo = agent_repo
    
    def assign_specialist(self, instance_id: int, phase_id: int,
                        specialist_id: int) -> None:
        """
        Specialist を Phase に割り当てる
        """
        # バリデーション
        self.validate_specialist(phase_id, specialist_id)
        
        # 割り当て
        self.specialist_repo.assign_specialist(
            instance_id, phase_id, specialist_id
        )
    
    def validate_specialist(self, phase_id: int, specialist_id: int) -> None:
        """
        Specialist が Phase の要件を満たしているか確認
        """
        phase = self.specialist_repo.get_phase(phase_id)
        specialist = self.agent_repo.get_agent(specialist_id)
        
        # Phase の specialist_type と Agent の role_type がマッチするか
        if specialist.role_type != phase.specialist_type:
            raise ValueError(
                f"Specialist role '{specialist.role_type}' does not match "
                f"required role '{phase.specialist_type}' for phase '{phase.phase_key}'"
            )
    
    def get_available_specialists(self, phase_id: int) -> list:
        """
        Phase に割り当て可能な Specialist を取得
        """
        phase = self.specialist_repo.get_phase(phase_id)
        specialists = self.agent_repo.get_agents_by_role(phase.specialist_type)
        return [s for s in specialists if s.is_active]
```

##### `TaskGenerationService` - タスク自動生成

```python
class TaskGenerationService:
    """タスク自動生成"""
    
    def __init__(self, task_repo, template_repo, specialist_repo):
        self.task_repo = task_repo
        self.template_repo = template_repo
        self.specialist_repo = specialist_repo
    
    def generate_tasks_for_instance(self, instance_id: int, template_id: int,
                                   specialist_assignments: dict) -> None:
        """
        インスタンス用タスクを自動生成
        
        Args:
            instance_id: workflow_instances.id
            template_id: 対象テンプレート ID
            specialist_assignments: specialist マッピング
        """
        # フェーズをソート
        phases = self.template_repo.get_phases(template_id)
        phases_sorted = sorted(phases, key=lambda p: p.phase_order)
        
        prev_phase_task_ids = []
        
        for phase in phases_sorted:
            # このフェーズの Specialist を取得
            specialist_id = specialist_assignments[phase.phase_key]
            specialist = self.specialist_repo.get_specialist(
                instance_id, phase.id
            )
            
            # 同フェーズのタスク定義を取得
            task_defs = self.template_repo.get_task_defs(phase.id)
            
            # フェーズ内タスク生成
            phase_task_ids = []
            for task_def in task_defs:
                # テンプレート置換
                title = task_def.task_title
                description = self._apply_placeholders(
                    task_def.task_description,
                    {
                        'specialist_name': specialist.specialist_name,
                        'phase_label': phase.phase_label,
                        'phase_key': phase.phase_key
                    }
                )
                
                # タスク作成
                task_id = self.task_repo.create_task(
                    title=title,
                    description=description,
                    status='pending',
                    priority=task_def.priority,
                    category=task_def.category,
                    phase=phase.phase_key,
                    assignee=specialist.specialist_slug,
                    workflow_instance_id=instance_id,
                    estimated_hours=task_def.estimated_hours
                )
                
                phase_task_ids.append(task_id)
                
                # wf_instance_nodes にリンク
                self.task_repo.link_node_to_task(
                    instance_id,
                    f"{phase.phase_key}_{task_def.task_key}",
                    task_id
                )
            
            # フェーズ内の依存関係を設定
            self._create_intra_phase_dependencies(
                task_defs, phase_task_ids
            )
            
            # フェーズ間の依存関係を設定
            if prev_phase_task_ids:
                for task_id in phase_task_ids:
                    for prev_task_id in prev_phase_task_ids:
                        self.task_repo.create_dependency(task_id, prev_task_id)
            
            prev_phase_task_ids = phase_task_ids
    
    def _apply_placeholders(self, template: str, context: dict) -> str:
        """プレースホルダを置換"""
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result
    
    def _create_intra_phase_dependencies(self, task_defs: list,
                                        task_ids: list) -> None:
        """
        同一フェーズ内のタスク依存関係を作成
        """
        # task_defs の depends_on_key を基に、task_ids 内の依存を設定
        task_key_to_id = {
            td.task_key: tid for td, tid in zip(task_defs, task_ids)
        }
        
        for task_def, task_id in zip(task_defs, task_ids):
            if task_def.depends_on_key:
                dep_task_id = task_key_to_id[task_def.depends_on_key]
                self.task_repo.create_dependency(task_id, dep_task_id)
```

##### `ValidationService` - バリデーション

```python
class ValidationService:
    """各種バリデーション"""
    
    @staticmethod
    def validate_template_schema(template_dict: dict) -> None:
        """テンプレート スキーマ検証"""
        required_fields = ['name', 'description']
        for field in required_fields:
            if field not in template_dict:
                raise ValueError(f"Missing required field: {field}")
    
    @staticmethod
    def validate_phase_order(phases: list) -> None:
        """フェーズ順序の妥当性確認（連続性、一意性）"""
        orders = [p.phase_order for p in phases]
        if sorted(orders) != list(range(1, len(orders) + 1)):
            raise ValueError("Phase orders must be continuous from 1")
    
    @staticmethod
    def validate_dependencies_dag(task_defs: list) -> None:
        """タスク依存グラフが DAG であることを確認"""
        # DFS で循環検出
        graph = {td.task_key: [td.depends_on_key] for td in task_defs
                 if td.depends_on_key}
        
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for task_key in graph:
            if task_key not in visited:
                if has_cycle(task_key):
                    raise ValueError("Circular dependency detected in tasks")
    
    @staticmethod
    def validate_specialist_assignments(template_id: int,
                                       specialist_assignments: dict,
                                       template_repo, agent_repo) -> None:
        """
        Specialist の割り当てが妥当か確認
        - すべての phase に specialist が割り当てられているか
        - specialist の role が phase の要件と合致するか
        """
        phases = template_repo.get_phases(template_id)
        
        # すべての phase がカバーされているか
        for phase in phases:
            if phase.phase_key not in specialist_assignments:
                raise ValueError(
                    f"Specialist not assigned for phase: {phase.phase_key}"
                )
        
        # 各 phase の specialist が要件を満たしているか
        for phase in phases:
            specialist_id = specialist_assignments[phase.phase_key]
            specialist = agent_repo.get_agent(specialist_id)
            
            if specialist.role_type != phase.specialist_type:
                raise ValueError(
                    f"Specialist {specialist.slug} role '{specialist.role_type}' "
                    f"does not match required role '{phase.specialist_type}' "
                    f"for phase '{phase.phase_key}'"
                )
```

### 2-3. Data Access Layer（データアクセス層）

#### 責務
- SQLite / KuzuDB への読み書き
- トランザクション管理
- 整合性制約の実装

#### 主要 Repository クラス

```python
class TemplateRepository:
    """テンプレート関連のデータアクセス"""
    
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def create_template(self, name: str, description: str) -> int:
        """テンプレートを作成"""
        cursor = self.conn.execute(
            """INSERT INTO workflow_templates (name, description, status, created_at, updated_at)
               VALUES (?, ?, 'draft', datetime('now','localtime'), datetime('now','localtime'))""",
            (name, description)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_phases(self, template_id: int) -> list:
        """フェーズを取得"""
        cursor = self.conn.execute(
            """SELECT id, phase_key, phase_order, phase_label, specialist_type, task_count,
                      is_parallel, config, description
               FROM wf_template_phases
               WHERE template_id = ?
               ORDER BY phase_order ASC""",
            (template_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_task_defs(self, phase_id: int) -> list:
        """タスク定義を取得"""
        cursor = self.conn.execute(
            """SELECT id, task_key, task_title, task_description, category,
                      estimated_hours, depends_on_key, priority
               FROM wf_template_tasks
               WHERE phase_id = ?""",
            (phase_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_prev_phase(self, template_id: int, phase_order: int):
        """前フェーズを取得"""
        cursor = self.conn.execute(
            """SELECT id, phase_key, phase_order FROM wf_template_phases
               WHERE template_id = ? AND phase_order = ?""",
            (template_id, phase_order - 1)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


class InstanceRepository:
    """インスタンス関連のデータアクセス"""
    
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def create_instance(self, template_id: int, name: str,
                       context: dict) -> int:
        """インスタンスを作成"""
        cursor = self.conn.execute(
            """INSERT INTO workflow_instances
               (template_id, name, status, context, created_at, updated_at)
               VALUES (?, ?, 'pending', ?, datetime('now','localtime'), datetime('now','localtime'))""",
            (template_id, name, json.dumps(context))
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def assign_specialist(self, instance_id: int, phase_id: int,
                        specialist_id: int, slug: str, name: str,
                        role: str) -> None:
        """Specialist を割り当て"""
        cursor = self.conn.execute(
            """SELECT phase_key FROM wf_template_phases WHERE id = ?""",
            (phase_id,)
        )
        phase_key = cursor.fetchone()[0]
        
        self.conn.execute(
            """INSERT INTO workflow_instance_specialists
               (instance_id, phase_id, phase_key, specialist_id,
                specialist_slug, specialist_name, specialist_role, assigned_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))""",
            (instance_id, phase_id, phase_key, specialist_id, slug, name, role)
        )
        self.conn.commit()


class TaskRepository:
    """タスク関連のデータアクセス"""
    
    def __init__(self, db_connection, graph_db):
        self.conn = db_connection
        self.graph_db = graph_db
    
    def create_task(self, **kwargs) -> int:
        """タスク作成"""
        cursor = self.conn.execute(
            """INSERT INTO dev_tasks
               (title, description, status, priority, category, phase, assignee,
                workflow_instance_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))""",
            (kwargs.get('title'), kwargs.get('description'),
             kwargs.get('status', 'pending'), kwargs.get('priority', 3),
             kwargs.get('category'), kwargs.get('phase'),
             kwargs.get('assignee'), kwargs.get('workflow_instance_id'))
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def create_dependency(self, task_id: int, depends_on_id: int) -> None:
        """依存関係を作成"""
        # SQLite に記録
        self.conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_id, created_at)
               VALUES (?, ?, datetime('now','localtime'))""",
            (task_id, depends_on_id)
        )
        self.conn.commit()
        
        # KuzuDB に同期
        self.graph_db.add_dependency(task_id, depends_on_id)
```

### 2-4. Infrastructure Layer（インフラ層）

#### 責務
- SQLite データベース管理
- KuzuDB グラフDB 管理
- トランザクション管理

#### DB 接続管理

```python
class DatabaseManager:
    """データベース接続・管理"""
    
    def __init__(self, db_path: str, graph_db_path: str):
        self.db_path = db_path
        self.graph_db_path = graph_db_path
        self.conn = None
        self.graph_db = None
    
    def connect(self):
        """接続を確立"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.graph_db = GraphDB(self.graph_db_path)
        self.ensure_schema()
    
    def ensure_schema(self):
        """スキーマが最新状態であることを保証"""
        # マイグレーション実行
        # ...
        pass
    
    def close(self):
        """接続を閉じる"""
        if self.conn:
            self.conn.close()
        if self.graph_db:
            self.graph_db.close()
```

---

## 3. モジュール設計

### 3-1. Python モジュール構成（推奨）

```
task-manager-sqlite/
├── scripts/
│   ├── task.py                           # CLI エントリポイント（既存）
│   │
│   └── workflow/                         # 新規モジュール
│       ├── __init__.py
│       ├── services/                     # ビジネスロジック
│       │   ├── __init__.py
│       │   ├── workflow_service.py       # WorkflowService
│       │   ├── specialist_service.py     # SpecialistAssignmentService
│       │   ├── task_generation_service.py # TaskGenerationService
│       │   └── validation_service.py     # ValidationService
│       │
│       ├── repositories/                 # データアクセス層
│       │   ├── __init__.py
│       │   ├── template_repository.py    # TemplateRepository
│       │   ├── instance_repository.py    # InstanceRepository
│       │   ├── specialist_repository.py  # SpecialistRepository
│       │   └── task_repository.py        # TaskRepository
│       │
│       ├── models/                       # データクラス
│       │   ├── __init__.py
│       │   ├── template.py               # Template クラス
│       │   ├── phase.py                  # Phase クラス
│       │   ├── instance.py               # Instance クラス
│       │   └── task.py                   # Task クラス
│       │
│       ├── exceptions/                   # 例外定義
│       │   ├── __init__.py
│       │   ├── validation_error.py
│       │   ├── not_found_error.py
│       │   └── state_error.py
│       │
│       └── cli/                          # CLI コマンド
│           ├── __init__.py
│           ├── template_commands.py      # wf template *
│           ├── instance_commands.py      # wf instance *
│           └── node_commands.py          # wf node *
```

### 3-2. 依存関係グラフ

```
cli.instance_commands
  ├─ services.workflow_service
  ├─ services.specialist_service
  ├─ services.task_generation_service
  └─ services.validation_service

services.workflow_service
  ├─ repositories.template_repository
  ├─ repositories.instance_repository
  └─ services.task_generation_service

services.task_generation_service
  ├─ repositories.task_repository
  ├─ repositories.template_repository
  └─ repositories.specialist_repository

repositories.*
  └─ models.*

models.*
  └─ （外部依存なし）
```

---

## 4. インターフェース定義

### 4-1. Service インターフェース

#### WorkflowService

```python
class WorkflowService:
    def create_template(name: str, description: str) -> int
    def instantiate_workflow(template_id: int, instance_name: str,
                            specialist_assignments: dict) -> int
    def advance_phase(instance_id: int, phase_key: str) -> None
    def get_instance_status(instance_id: int) -> dict
    def get_template_info(template_id: int) -> dict
    def list_templates(status: str = None) -> list
    def list_instances(template_id: int = None) -> list
```

#### SpecialistAssignmentService

```python
class SpecialistAssignmentService:
    def assign_specialist(instance_id: int, phase_id: int, 
                         specialist_id: int) -> None
    def validate_specialist(phase_id: int, specialist_id: int) -> None
    def get_available_specialists(phase_id: int) -> list
    def get_assigned_specialist(instance_id: int, phase_id: int) -> dict
```

#### TaskGenerationService

```python
class TaskGenerationService:
    def generate_tasks_for_instance(instance_id: int, template_id: int,
                                   specialist_assignments: dict) -> None
    def get_tasks_for_instance(instance_id: int) -> list
    def advance_task(task_id: int, next_status: str) -> None
```

---

## 5. エラーハンドリング & 例外設計

### 5-1. 例外階層

```python
class WorkflowException(Exception):
    """基底例外"""
    pass

class ValidationError(WorkflowException):
    """バリデーション失敗"""
    pass

class SpecialistAssignmentError(ValidationError):
    """Specialist 割り当てエラー"""
    pass

class TemplateNotFoundError(WorkflowException):
    """テンプレートが見つからない"""
    pass

class InstanceNotFoundError(WorkflowException):
    """インスタンスが見つからない"""
    pass

class InvalidStateTransitionError(WorkflowException):
    """不正なステータス遷移"""
    pass

class CircularDependencyError(ValidationError):
    """循環依存を検出"""
    pass
```

### 5-2. エラーハンドリング戦略

```python
# CLI レベルでのハンドリング
def cmd_wf_instance_start(template_id, name, specialist_json):
    try:
        service = get_workflow_service()
        specialist_assignments = json.loads(specialist_json)
        instance_id = service.instantiate_workflow(
            template_id, name, specialist_assignments
        )
        print(f"✓ Instance created: {instance_id}")
    except ValidationError as e:
        print(f"✗ Validation error: {e}", file=sys.stderr)
        sys.exit(1)
    except TemplateNotFoundError as e:
        print(f"✗ Template not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
```

---

*このドキュメントは、Phase 3 向けのシステムアーキテクチャを定義しています。*
*次ステップ：flow-design.md（処理フロー設計）を参照。*
