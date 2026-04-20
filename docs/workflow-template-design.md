# ワークフローテンプレートシステム - Phase 2 技術設計

**作成日**: 2026-04-18  
**バージョン**: v1.0  
**ステータス**: 設計中（Phase 2）

---

## 目次

1. [ワークフローテンプレートスキーマ設計](#1-ワークフローテンプレートスキーマ設計)
2. [インスタンス化メカニズム設計](#2-インスタンス化メカニズム設計)
3. [自動タスク生成設計](#3-自動タスク生成設計)

---

## 1. ワークフローテンプレートスキーマ設計

### 1-1. 既存テーブル構造の確認

task-manager-sqlite v2 では以下のワークフロー関連テーブルが既に実装されている:

#### `workflow_templates` テーブル
テンプレートのメタデータを管理する:

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT NOT NULL | テンプレート名（例: "Product Launch"） |
| description | TEXT | テンプレート説明 |
| version | INTEGER DEFAULT 1 | バージョン |
| status | TEXT | draft / active / deprecated |
| created_at | TEXT | 作成日時 |
| updated_at | TEXT | 更新日時 |

#### `wf_template_nodes` テーブル
テンプレート内のノード（フェーズ・ステップ）を定義:

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | |
| template_id | INTEGER FK | → workflow_templates.id |
| node_key | TEXT | テンプレート内一意キー（例: 'planning', 'dev-phase-1'） |
| node_type | TEXT | `start` / `end` / `task` / `gateway_xor` / `gateway_and_split` / `gateway_and_join` |
| label | TEXT | 表示名（例: "Planning Phase"） |
| role | TEXT | 担当ロール（例: "em"） |
| persona | TEXT | 担当ペルソナ（例: "pm-alice"） |
| description | TEXT | フェーズ説明 |
| config | TEXT | JSON（追加設定、フェーズの順序・条件等） |
| UNIQUE | | (template_id, node_key) |

#### `wf_template_edges` テーブル
ノード間の遷移・依存関係を定義:

| カラム | 型 | 説明 |
|---|---|---|
| id | INTEGER PK | |
| template_id | INTEGER FK | → workflow_templates.id |
| from_node_id | INTEGER FK | → wf_template_nodes.id |
| to_node_id | INTEGER FK | → wf_template_nodes.id |
| condition | TEXT | NULL=無条件 / 例: result=='passed' |
| condition_label | TEXT | 条件の説明（例: "テスト合格時"） |
| priority | INTEGER DEFAULT 0 | XOR分岐の評価順 |

### 1-2. ワークフローテンプレートスキーマの拡張設計

既存テーブルを基にして、**Phase ベース**のテンプレート構造を実装する。

#### 新規テーブル: `wf_template_phases`
フェーズレベルのメタデータを管理（タスク生成時に必要）:

```sql
CREATE TABLE IF NOT EXISTS wf_template_phases (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id       INTEGER NOT NULL REFERENCES workflow_templates(id),
    phase_key         TEXT NOT NULL,           -- 'planning', 'development', 'testing', 'deployment'
    phase_order       INTEGER NOT NULL,        -- フェーズの実行順序（1, 2, 3, ...）
    phase_label       TEXT NOT NULL,           -- 表示名
    specialist_type   TEXT NOT NULL,           -- 'pm', 'engineer', 'qa', 'devops' 等
    specialist_count  INTEGER DEFAULT 1,       -- このフェーズに割り当てるスペシャリスト数
    task_count        INTEGER NOT NULL,        -- このフェーズで生成するタスク数
    description       TEXT,
    estimated_hours   INTEGER,                 -- 見積もり時間
    is_parallel       BOOLEAN DEFAULT 0,       -- 前フェーズと並列実行可能か
    config            TEXT,                    -- JSON（追加設定）
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(template_id, phase_key)
);
```

#### 拡張: `wf_template_nodes` に `phase_key` カラムを追加

```sql
ALTER TABLE wf_template_nodes ADD COLUMN phase_key TEXT;  -- フェーズへのリンク
```

これにより、ノード（task type）がどのフェーズに属するかを明示的に表現できる。

#### タスク定義テーブル: `wf_template_tasks`
フェーズ内のタスク定義（タスク自動生成時のテンプレート）:

```sql
CREATE TABLE IF NOT EXISTS wf_template_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_id          INTEGER NOT NULL REFERENCES wf_template_phases(id),
    template_id       INTEGER NOT NULL REFERENCES workflow_templates(id),
    task_key          TEXT NOT NULL,           -- 'design-arch', 'implement-api', 'test-unit' 等
    task_title        TEXT NOT NULL,           -- タスク表示名
    task_description  TEXT,                    -- タスク説明テンプレート（{specialist_name} 等のプレースホルダ可）
    category          TEXT,                    -- dev_tasks.category に対応（'design', 'implement', 'test' 等）
    estimated_hours   INTEGER,                 -- 見積もり時間
    depends_on_key    TEXT,                    -- 依存タスクキー（NULL = 並列実行可能）
    priority          INTEGER DEFAULT 3,       -- 優先度（1=高, 2=中, 3=低）
    created_at        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(phase_id, task_key)
);
```

### 1-3. スキーマ設計の要点

| 項目 | 設計 |
|---|---|
| **テンプレート定義** | workflow_templates（メタデータ） + wf_template_phases（フェーズ定義） + wf_template_tasks（タスク定義） |
| **フェーズ構造** | `phase_order` で順序を定義。is_parallel で前フェーズとの並列性を制御 |
| **スペシャリスト割り当て** | `wf_template_phases.specialist_type` で担当ロール定義。インスタンス化時に具体的なペルソナを割り当て |
| **タスク自動生成テンプレート** | `wf_template_tasks` に title_template・description_template を定義。プレースホルダで動的置換 |
| **順序依存性** | `wf_template_tasks.depends_on_key` で同一フェーズ内のタスク依存関係を定義 |

---

## 2. インスタンス化メカニズム設計

### 2-1. インスタンス化フロー（概要）

```
Workflow Template
  ↓
  └─ フェーズ定義を読み込む (wf_template_phases)
  └─ タスク定義を読み込む (wf_template_tasks)
  ↓
Specialist Assignment
  ├─ 各フェーズに割り当てるスペシャリストを決定（agents テーブルから select）
  └─ phase_order に従って specialist_id/slug を決定
  ↓
Workflow Instance 作成
  ├─ workflow_instances レコード作成
  └─ context に specialist_assignments を JSON で保存
  ↓
Phase Instance 作成 (wf_instance_nodes)
  └─ wf_template_phases ごとに node_key を生成
  └─ status = 'waiting' / 'ready' で初期化
  ↓
Task 自動生成 (dev_tasks)
  ├─ phase_order に従い、各フェーズのタスク定義から dev_tasks を生成
  ├─ 生成タスク間の依存関係を task_dependencies に設定
  └─ task_id を wf_instance_nodes に記録
```

### 2-2. Specialist Assignment メカニズム

#### データ構造: `workflow_instance_specialists`（新規）

```sql
CREATE TABLE IF NOT EXISTS workflow_instance_specialists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id       INTEGER NOT NULL REFERENCES workflow_instances(id),
    phase_id          INTEGER NOT NULL REFERENCES wf_template_phases(id),
    phase_key         TEXT NOT NULL,
    specialist_id     INTEGER NOT NULL REFERENCES agents(id),
    specialist_slug   TEXT NOT NULL,           -- agents.slug（例: "em-alice"）
    specialist_name   TEXT NOT NULL,           -- agents.name（表示用）
    specialist_role   TEXT NOT NULL,           -- agents.role_type（'em', 'engineer', 'qa'）
    assigned_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(instance_id, phase_id)
);
```

#### インスタンス化時の Specialist 割り当てアルゴリズム

1. **フェーズごとに必要なロールを確認**:
   ```python
   for phase in template.phases:
       required_role = phase.specialist_type  # 'em', 'engineer', 'qa', 'devops'
   ```

2. **利用可能なエージェント（agents テーブル）から検索**:
   ```python
   available_agents = query_agents(role_type=required_role, is_active=True)
   ```

3. **割り当て戦略**:
   - **方式 1（ラウンドロビン）**: 複数フェーズに同じ specialist を分散割り当て
   - **方式 2（集約）**: 同じ specialist に複数フェーズを割り当て（タスク数が少ない場合）
   - **方式 3（ユーザー指定）**: インスタンス化時に specialist を明示的に指定

   設計上は**方式 3（ユーザー指定）**を採用する。理由：
   - テンプレートが汎用的である一方、実際の specialist 割り当てはコンテキスト依存
   - instance_id ごとに異なる specialist 組合せをテスト可能

### 2-3. フェーズ順序制御メカニズム

#### Phase 実行ステート遷移

```
(初期)
[waiting] ─────────────────────────────────────────────┐
                                                        │
                      (前フェーズの全タスク完了)
                                                        │
                                                        v
                                                    [ready]
                                                        │
                                          (フェーズリーダーがstart)
                                                        │
                                                        v
                                                  [running]
                                                        │
                                        (全タスク completed)
                                                        │
                                                        v
                                                 [completed]
```

#### 実装: `wf_instance_nodes.status` の遷移ロジック

```python
def advance_phase(instance_id: int, phase_node_id: int):
    """
    フェーズを waiting → ready → running → completed に遷移させる。
    前フェーズの全タスク完了を確認してから ready に遷移する。
    """
    phase_node = get_phase_node(phase_node_id)
    
    # 前フェーズの確認
    prev_phase = get_prev_phase(phase_node.phase_order)
    if prev_phase:
        if not all_tasks_completed(instance_id, prev_phase.id):
            raise ValueError(f"Phase '{prev_phase.phase_key}' is not completed yet")
    
    # ready に遷移
    update_phase_status(phase_node_id, 'ready')
```

### 2-4. インスタンス化 SQL 実装例

```python
def instantiate_workflow(template_id: int, instance_name: str, specialist_assignments: dict) -> int:
    """
    template_id から workflow instance を生成する。
    
    Args:
        template_id: workflow_templates.id
        instance_name: インスタンス名（例: "Product Launch #1"）
        specialist_assignments: {phase_key: specialist_id} のdict
    
    Returns:
        新規作成した workflow_instances.id
    """
    conn = get_db_connection()
    
    # 1. workflow_instances レコード作成
    instance_id = conn.execute("""
        INSERT INTO workflow_instances (template_id, name, status, context, created_at, updated_at)
        VALUES (?, ?, 'pending', ?, datetime('now','localtime'), datetime('now','localtime'))
    """, (template_id, instance_name, json.dumps({'specialist_assignments': specialist_assignments}))).lastrowid
    
    # 2. フェーズ情報取得
    phases = conn.execute("""
        SELECT id, phase_key, phase_order, specialist_type, task_count
        FROM wf_template_phases
        WHERE template_id = ?
        ORDER BY phase_order ASC
    """, (template_id,)).fetchall()
    
    # 3. specialist_assignments テーブルに記録
    for phase in phases:
        specialist_id = specialist_assignments.get(phase['phase_key'])
        specialist_info = conn.execute("""
            SELECT id, slug, name, role_type FROM agents WHERE id = ?
        """, (specialist_id,)).fetchone()
        
        conn.execute("""
            INSERT INTO workflow_instance_specialists
            (instance_id, phase_id, phase_key, specialist_id, specialist_slug, specialist_name, specialist_role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (instance_id, phase['id'], phase['phase_key'], specialist_id,
              specialist_info['slug'], specialist_info['name'], specialist_info['role_type']))
    
    conn.commit()
    return instance_id
```

---

## 3. 自動タスク生成設計

### 3-1. タスク生成フロー

```
Workflow Instance インスタンス化完了
  ↓
各フェーズを phase_order でソート
  ↓
フェーズごと（順序）にタスクを生成
  ├─ wf_template_tasks から タスク定義を読み込む
  ├─ specialist 情報を workflow_instance_specialists から取得
  ├─ dev_tasks にレコード作成
  └─ task_dependencies に依存関係を記録
  ↓
  └─ wf_instance_nodes.task_id に dev_tasks.id をリンク
```

### 3-2. タスク自動生成アルゴリズム

#### Step 1: フェーズごとにタスク定義を読み込む

```python
def generate_tasks_for_workflow_instance(instance_id: int):
    """
    workflow instance のタスクを自動生成する。
    """
    conn = get_db_connection()
    
    # インスタンスとテンプレート情報を取得
    instance = conn.execute("""
        SELECT wi.id, wi.template_id, wi.name FROM workflow_instances wi
        WHERE wi.id = ?
    """, (instance_id,)).fetchone()
    
    # フェーズを phase_order でソート
    phases = conn.execute("""
        SELECT id, phase_key, phase_order, task_count FROM wf_template_phases
        WHERE template_id = ?
        ORDER BY phase_order ASC
    """, (instance['template_id'],)).fetchall()
    
    # 前フェーズのタスクID（依存関係設定用）
    prev_phase_task_ids = []
    
    for phase in phases:
        phase_id = phase['id']
        phase_key = phase['phase_key']
        
        # specialist 情報を取得
        specialist = conn.execute("""
            SELECT specialist_id, specialist_slug, specialist_name
            FROM workflow_instance_specialists
            WHERE instance_id = ? AND phase_id = ?
        """, (instance_id, phase_id)).fetchone()
        
        # フェーズ内のタスク定義を取得
        task_defs = conn.execute("""
            SELECT task_key, task_title, task_description, category, estimated_hours, depends_on_key, priority
            FROM wf_template_tasks
            WHERE phase_id = ?
            ORDER BY task_key ASC
        """, (phase_id,)).fetchall()
        
        # Phase 内のタスクを生成
        phase_task_ids = []
        for task_def in task_defs:
            # タスク作成
            task_id = conn.execute("""
                INSERT INTO dev_tasks
                (title, description, status, priority, category, phase, assignee, project, created_at, updated_at)
                VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
            """, (
                task_def['task_title'],
                task_def['task_description'] or f"Task in {phase_key}",
                task_def['priority'],
                task_def['category'] or 'general',
                phase_key,
                specialist['specialist_slug'],
                instance['name']
            )).lastrowid
            
            phase_task_ids.append(task_id)
            
            # Task を wf_instance_nodes にリンク
            conn.execute("""
                INSERT INTO wf_instance_nodes (instance_id, node_key, status, task_id, created_at)
                VALUES (?, ?, 'ready', ?, datetime('now','localtime'))
            """, (instance_id, f"{phase_key}_{task_def['task_key']}", task_id))
        
        # フェーズ内のタスク依存関係を設定
        for task_def in task_defs:
            if task_def['depends_on_key']:
                # 依存先タスクを検索
                dep_task = next(
                    (t for t in task_defs if t['task_key'] == task_def['depends_on_key']),
                    None
                )
                if dep_task:
                    # タスク ID マッピングを使用（実装詳細）
                    pass  # TODO: タスク ID マッピング
        
        # 前フェーズタスクへの依存設定（フェーズ順序制御）
        if prev_phase_task_ids:
            for task_id in phase_task_ids:
                for prev_task_id in prev_phase_task_ids:
                    conn.execute("""
                        INSERT INTO task_dependencies (task_id, depends_on_id, created_at)
                        VALUES (?, ?, datetime('now','localtime'))
                    """, (task_id, prev_task_id))
        
        prev_phase_task_ids = phase_task_ids
        conn.commit()
```

### 3-3. 順序依存性の実装

#### ルール 1: フェーズレベルの順序制御

```
Phase 1 の全タスク完了
    ↓
Phase 2 のタスク群が blocked → pending に遷移（unblock_successors 呼び出し）
    ↓
Phase 2 の全タスク完了
    ↓
Phase 3 の遷移...
```

#### ルール 2: フェーズ内タスクの依存関係

```python
# task_defs から depends_on_key を参照し、同一フェーズ内の依存を設定
for task_def in phase_task_defs:
    if task_def['depends_on_key']:
        # 例: 'test-api' が 'implement-api' に依存
        dep_task_def = find_task_def(phase_id, task_def['depends_on_key'])
        
        # dev_tasks 上で依存関係を追加
        conn.execute("""
            INSERT INTO task_dependencies (task_id, depends_on_id, created_at)
            VALUES (?, ?, datetime('now','localtime'))
        """, (task_id, dep_task_id))
```

### 3-4. タスク生成時の専門家アサイン

```python
# specialist_slug をそのまま assignee に設定
task_id = conn.execute("""
    INSERT INTO dev_tasks
    (..., assignee, phase, ...)
    VALUES (..., ?, ?, ...)
""", (specialist['specialist_slug'], phase_key))

# あるいは、新しいロール体系を採用する場合:
conn.execute("""
    INSERT INTO dev_tasks
    (..., practitioner_id, practitioner_status, ...)
    VALUES (..., ?, 'pending', ...)
""", (specialist['specialist_id'],))
```

### 3-5. 自動タスク生成の冪等性

インスタンス化時に既にタスクが生成されている場合は、重複を避けるため以下を確認:

```python
def generate_tasks_for_workflow_instance(instance_id: int):
    # 既にタスクが生成されているか確認
    existing_task_count = conn.execute("""
        SELECT COUNT(*) FROM wf_instance_nodes
        WHERE instance_id = ? AND task_id IS NOT NULL
    """, (instance_id,)).fetchone()[0]
    
    if existing_task_count > 0:
        raise ValueError(f"Instance {instance_id} already has tasks. Use update to modify.")
```

---

## 4. 実装チェックリスト（Phase 3 へ向けて）

### スキーマ設計の確認項目

- [ ] `wf_template_phases` テーブル設計の妥当性確認
- [ ] `wf_template_tasks` テーブル設計の妥当性確認
- [ ] `workflow_instance_specialists` テーブル設計の妥当性確認
- [ ] プレースホルダ機構（task_description テンプレート）の実装方式決定
- [ ] マイグレーション SQL の準備

### インスタンス化メカニズムの確認項目

- [ ] specialist assignment の UI/API 設計
- [ ] phase_order に基づく順序制御の実装方式確認
- [ ] 並列フェーズ（is_parallel）の制御方式確認
- [ ] エラーハンドリング（前フェーズ未完了時の処理）

### 自動タスク生成の確認項目

- [ ] task_defs から dev_tasks への マッピング仕様確認
- [ ] タスク内依存関係（depends_on_key）の実装方式確認
- [ ] フェーズ間依存関係の実装（すべての前フェーズタスク完了待ち）
- [ ] 冪等性の保証方式確認
- [ ] テスト戦略の検討（単体 / 統合 / E2E）

---

## 5. 設計からの重要な決定事項

| 項目 | 決定 | 理由 |
|---|---|---|
| **テンプレート構造** | wf_template_phases + wf_template_tasks の 2 段階 | フェーズごとのメタデータ管理が必要 |
| **Specialist 割り当て** | ユーザー指定（方式 3） | インスタンスごとの異なる specialist 組合せをサポート |
| **順序制御** | task_dependencies + phase_order | 既存の task-manager-sqlite 構造を活用 |
| **タスク生成** | instance 作成時に一括生成 | 遅延生成よりシンプル・予測可能 |
| **冪等性** | instance ごとに一度のみ生成 | 重複防止・トレーサビリティ向上 |

---

*このドキュメントは Phase 2 の技術設計をまとめたものです。Phase 3 では、このスキーマ・メカニズムに基づいて実装を進めます。*
