# features/agent_delegation.feature
Feature: エージェント委譲API
  プロダクトマネージャーとして
  AIエージェントにタスクを委譲したい
  そのためにエージェント委譲APIを通じてタスク割り当てと実行状況を管理できる

  Background:
    Given エージェントが作成されている
    And 部署が初期化されている

  Scenario: エージェントへのタスク委譲
    Given エージェント ID が「agent_001」である
    And 委譲するタスクが以下の内容である:
      | キー | 値 |
      | title | リード発掘 |
      | description | B2B リード 100社の発掘 |
      | budget | 500000 |
      | deadline | 2026-04-29 |

    When POST /api/agents/delegate にリクエストを送信する
    Then ステータスコード 200 が返される
    And レスポンスに以下が含まれている:
      | フィールド | 値 |
      | agent_id | agent_001 |
      | task_id | task_* |
      | status | assigned |
    And データベースに委譲レコードが保存される

  Scenario: エージェントのタスク一覧取得
    Given エージェント ID が「agent_002」である
    And エージェントに 3 つのタスクが割り当てられている

    When GET /api/agents/agent_002/tasks をリクエストする
    Then ステータスコード 200 が返される
    And レスポンスに task_id、title、status を含むタスク配列が返される
    And タスク数が 3 である

  Scenario: 部署メトリクスの取得
    Given 部署 ID が「dept_sales」である
    And 複数のエージェントがタスクを実行している

    When GET /api/departments/dept_sales/metrics をリクエストする
    Then ステータスコード 200 が返される
    And レスポンスに以下が含まれている:
      | フィールド | 値 |
      | dept_id | dept_sales |
      | total_tasks | 整数 |
      | completed_tasks | 整数 |
      | completion_rate | 0.0-1.0 |
      | avg_task_duration | 整数 |

  Scenario: エージェント委譲のエラーハンドリング
    Given エージェント ID が「agent_invalid」である

    When 無効なエージェント ID で POST /api/agents/delegate をリクエストする
    Then ステータスコード 400 または 404 が返される
    And エラーメッセージが返される

  Scenario Outline: 複数エージェントへの並列委譲
    Given <agent_count> 個のエージェントが存在する

    When 各エージェントに異なるタスクを委譲する
    Then <agent_count> 個のタスク割り当てが成功する
    And 各エージェントが独立したタスク ID を取得する

    Examples:
      | agent_count |
      | 2 |
      | 3 |
      | 5 |

  Scenario: エージェント委譲のステータス追跡
    Given タスク ID が「task_123」であり、エージェント ID が「agent_003」である

    When タスク割り当て直後に GET /api/agents/agent_003/tasks をリクエストする
    Then task_123 のステータスが「assigned」である

    When エージェントがタスクを実行し、ステータスが「in_progress」に更新される
    And 再度 GET /api/agents/agent_003/tasks をリクエストする
    Then task_123 のステータスが「in_progress」である

    When エージェントがタスクを完了し、ステータスが「completed」に更新される
    And 再度 GET /api/agents/agent_003/tasks をリクエストする
    Then task_123 のステータスが「completed」である
