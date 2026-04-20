# BDD テストコード構成設計ドキュメント

## 概要

このディレクトリは、ワークフロー管理システムのBDD（Behavior-Driven Development）テストスイートです。pytest-bdd を使用して Gherkin 形式のテストシナリオを実行します。

## ディレクトリ構成

```
tests/workflow/bdd/
├── __init__.py                           # Package marker
├── conftest.py                           # Fixtures & shared setup
├── test_workflow_bdd.py                  # BDD scenario mappings
├── step_definitions/
│   ├── __init__.py
│   └── steps.py                          # Step implementations
└── README.md                             # This file

features/
├── workflow.feature                      # Main Gherkin feature file
├── workflow-uat.feature                  # UAT scenarios (Phase 8)
└── workflow-template.feature             # Template scenarios (legacy)
```

## テストの実行方法

### すべての BDD テストを実行

```bash
pytest tests/workflow/bdd/test_workflow_bdd.py -v
```

### 特定のシナリオのみ実行

```bash
pytest tests/workflow/bdd/test_workflow_bdd.py::test_create_workflow_template -v
```

### Feature ファイルから直接実行

```bash
pytest --gherkin-terminal-reporter features/workflow.feature
```

### Verbose モード（ステップの詳細表示）

```bash
pytest tests/workflow/bdd/ -vv --tb=short
```

## Fixture と Shared Context

### BDD Context (`bdd_context`)

すべてのシナリオ間で共有される状態を保持:

```python
class BDDContext:
    templates: dict[str, Template]         # テンプレート (名前 → オブジェクト)
    instances: dict[str, Instance]         # インスタンス
    phases: dict[str, Phase]               # フェーズ
    tasks: dict[str, list[Task]]           # 各フェーズのタスク
    specialists: dict[str, Agent]          # 専門家（メール → Agent）
    validation_errors: list[str]           # バリデーション エラー
    task_count: int                        # 生成されたタスク総数
```

### Service Fixtures

- `template_service`: TemplateService - テンプレート管理
- `instance_service`: WorkflowInstanceService - インスタンス・タスク生成
- `specialist_repo`: SpecialistRepository - 専門家管理
- `temp_db`: 一時的なテスト用 SQLite データベース

### Database Fixtures

自動的に以下のテーブルが作成されます:

- `workflow_templates` - テンプレート定義
- `wf_template_phases` - テンプレート内のフェーズ
- `wf_template_tasks` - テンプレート内のタスク定義
- `agents` - 専門家（PM、エンジニア、QA）
- `workflow_instances` - テンプレートから生成されたインスタンス
- `wf_instance_nodes` - インスタンス内のフェーズノード
- `workflow_instance_specialists` - フェーズ専門家割り当て
- `dev_tasks` - 生成された開発タスク
- `task_dependencies` - タスク間の依存関係
- `audit_logs` - 状態変更の監査ログ

## Gherkin シナリオ設計

### シナリオ分類

#### 1. テンプレート作成
- `Create workflow template with sequential phases`
- `Add tasks to template phases`
- `Validate template completeness before instantiation`

#### 2. インスタンス化
- `Instantiate template with specialist assignments`
- `Auto-generate tasks during instantiation`
- `Validate specialist assignment before instantiation`

#### 3. フェーズ実行
- `Execute first phase with sequential unlock`
- `Phase transition with notification`
- `Block phase transition on incomplete tasks`

#### 4. タスク生成・割り当て
- `Generate development tasks from template tasks`
- `Task assignment based on phase specialist`
- `Task dependency tracking`

#### 5. 委譲チェーン
- `Delegation chain initialization`
- `Task assignment to engineer in delegation chain`
- `Engineer task completion tracking`

#### 6. エラーハンドリング
- `Recover from validation failure during instantiation`
- `Handle concurrent task completion`
- `Rollback on phase transition error`

#### 7. 監査・コンプライアンス
- `Audit log all state changes`
- `Compliance: no tasks created outside workflow phase`
- `Data integrity: cascade delete prevents orphans`

#### 8. ステータス集約・監視
- `Aggregate workflow status from phase states`
- `Monitor phase progress in real-time`
- `List active workflows with phase breakdown`

### Given/When/Then パターン

#### Background（全シナリオ共通）

```gherkin
Background:
  Given the workflow system is initialized
  And a test specialist directory exists with:
    | Email         | Name            | Specialist Type |
    | pm@company    | Project Manager | pm              |
    | eng@company   | Lead Engineer   | engineer        |
    | qa@company    | QA Engineer     | qa              |
```

#### テンプレート作成例

```gherkin
Scenario: Create workflow template with sequential phases
  When I create a workflow template named "Development Process"
  And I add phase "Requirements" with specialist type "pm" (sequential)
  And I add phase "Implementation" with specialist type "engineer" (sequential)
  And I add phase "Testing" with specialist type "qa" (sequential)
  Then the template should have 3 phases in order
  And all phases should be marked sequential
```

#### インスタンス化例

```gherkin
Scenario: Instantiate template with specialist assignments
  Given a workflow template named "QA Release" with 3 phases and 7 tasks
  When I instantiate the template with specialist assignments:
    | Phase Name      | Assigned Specialist |
    | Requirements    | pm@company          |
    | Implementation  | eng@company         |
    | Testing         | qa@company          |
  Then a workflow instance should be created
  And all 3 phases should be initialized as phase instances
```

## Step 実装パターン

### Given ステップ（前提条件）

```python
@given(parsers.parse('a workflow template named "{template_name}"'))
def template_exists(template_service, bdd_context, template_name):
  template = template_service.create_template(
    name=template_name,
    created_by="test@example.com"
  )
  bdd_context.current_template = template
```

### When ステップ（アクション）

```python
@when(parsers.parse('I instantiate the template with specialist assignments:'))
def instantiate_template(instance_service, bdd_context, table):
  instance = instance_service.create_instance(
    template_id=bdd_context.current_template.id,
    name=f"{bdd_context.current_template.name} Instance",
    specialist_assignments={row['Phase Name']: row['Assigned Specialist'] for row in table}
  )
  bdd_context.current_instance = instance
```

### Then ステップ（検証）

```python
@then('a workflow instance should be created')
def verify_instance_created(bdd_context):
  assert bdd_context.current_instance is not None
  assert bdd_context.current_instance.id is not None
```

## テスト実行時の注意事項

### 1. データベース分離

各テスト関数は独立した一時データベースを使用します。テスト間でのデータ汚染は発生しません。

```python
def test_example(temp_db):  # 自動的に新しいDBが作成される
    # テスト実行
    pass
    # テスト終了時に自動削除
```

### 2. Context の生存期間

`bdd_context` は各テスト関数スコープで新規作成され、テスト終了時に廃棄されます。

```python
def test_template_creation(bdd_context):
  # bdd_context は新規インスタンス
  template = ...
  assert bdd_context.templates[...] == template
  # テスト終了 → bdd_context 破棄
```

### 3. テーブル解析

Gherkin テーブルは自動的に dict リストに変換されます:

```gherkin
When I have specialists:
  | Email         | Name            | Type      |
  | pm@company    | Project Manager | pm        |
```

```python
def step_function(table):
  for row in table:
    email = row['Email']      # "pm@company"
    name = row['Name']        # "Project Manager"
    spec_type = row['Type']   # "pm"
```

## 拡張ガイドライン

### 新しいシナリオの追加

1. `features/workflow.feature` に Gherkin シナリオを追加
2. `test_workflow_bdd.py` に `@scenario()` デコレータで対応するテスト関数を追加
3. `step_definitions/steps.py` に新しい Given/When/Then ステップを実装

### テスト実行性

各 Given/When/Then ステップは以下の条件を満たすべき:

- ✅ 単体テスト可能（モック依存関係が使用可能）
- ✅ 再利用可能（複数のシナリオで使用）
- ✅ 明確な入出力（fixtures と戻り値で追跡可能）
- ✅ エラーメッセージが具体的（assertion で詳細情報を提供）

## テストコード品質基準

### カバレッジ対象

- ✅ テンプレート作成・検証
- ✅ インスタンス化・自動タスク生成
- ✅ フェーズ実行・遷移
- ✅ 委譲チェーン
- ✅ エラーハンドリング・復旧
- ✅ 監査ログ・コンプライアンス

### 実装状態

| シナリオ | 状態 | 実装者 |
|---|---|---|
| Template Creation | ✅ Designed | system |
| Instance Creation | ✅ Designed | system |
| Phase Execution | 🔄 Partial | TBD |
| Task Generation | ✅ Designed | system |
| Delegation Chain | 🔄 Partial | TBD |
| Error Handling | 🔄 Partial | TBD |
| Audit & Compliance | ✅ Designed | system |

## 参考資料

- **pytest-bdd Documentation**: https://pytest-bdd.readthedocs.io/
- **Gherkin Reference**: https://cucumber.io/docs/gherkin/
- **Phase 8 E2E Tests**: `tests/workflow/e2e/test_scenarios.py`
- **Integration Tests**: `tests/workflow/integration/`
