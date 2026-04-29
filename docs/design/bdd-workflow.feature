Feature: BDD業務フロー管理
  BDD の原則に従い、ワークフロー全体（テンプレート→インスタンス→フェーズ→タスク→アサイン）
  を段階的に実行し、マルチエージェント業務フローを自動化する。

  Background:
    Given task-manager-sqlite が稼働している
    And orchestrator がスタンバイ状態である
    And tmux に "ai-orchestrator@main" セッションが存在する

  # ────────────────────────────────────────────────────────
  # Scenario 1: ワークフロー テンプレート作成
  # ────────────────────────────────────────────────────────

  Scenario: テンプレート作成と保存
    Given ワークフロー定義が ".feature" ファイルに記述されている
    When orchestrator が "development-workflow" テンプレートをロードする
    Then テンプレートの5つのフェーズ (Setup/Planning/Impl/Verify/Complete) が定義されている
    And テンプレート ID が SQLite に保存される
    And Gherkin ステップ定義が実行可能になる

  # ────────────────────────────────────────────────────────
  # Scenario 2: ワークフローインスタンス化と自動分割
  # ────────────────────────────────────────────────────────

  Scenario: テンプレートからワークフローインスタンスを作成
    Given テンプレート "development-workflow" が存在する
    When orchestrator が新プロジェクト "exp-stock" に対してインスタンスを作成する
    Then workflow_id = 1 が SQLite に記録される
    And 5つのフェーズが自動生成される
    And Phase 1 (Setup) が最初に開始される
    And Phase 1 には「タスク分析」「専門家決定」等の初期タスクが自動生成される

  # ────────────────────────────────────────────────────────
  # Scenario 3: フェーズ遷移と タスク DAG 実行
  # ────────────────────────────────────────────────────────

  Scenario: フェーズ遷移とタスク依存関係の自動追跡
    Given workflow_id = 1 が Phase 1 (Setup) で pending 状態
    And Phase 1 の全タスク (task_2055, task_2056) が定義されている
    When task_2055 と task_2056 が completed となる
    Then orchestrator が Phase 1 を自動的に completed にマークする
    And Phase 2 (Planning) の開始条件がチェックされる
    And 依存タスク (task_2057, task_2058) が pending に遷移する
    And orchestrator が EM に "Phase 2 開始" をアサインする

  # ────────────────────────────────────────────────────────
  # Scenario 4: Engineer へのタスク実行と完了報告
  # ────────────────────────────────────────────────────────

  Scenario: タスク実行フロー（orchestrator → EM → Engineer → 完了）
    Given task_2058 が pending 状態で "BDD設計書作成" というタイトル
    And task_2058 の担当者が未決定
    When orchestrator が task_2058 をEM にアサインする
    Then EM セッション "em@exp-stock" が新規作成される
    And ccc-engineering-manager が起動される
    And EM が task_2058 の requirements を確認する
    When EM が engineer セッション "eng@exp-stock-task2058" を作成する
    And ENGINEER_PERSONA="..." で ccc-engineer を起動する
    And Engineer が BDD-Architecture.md と bdd-workflow.feature を作成する
    When Engineer が `python3 task.py done 2058` を実行する
    Then task_2058 のステータスが completed に変更される
    And orchestrator が次の依存タスク (task_2059) を pending に遷移させる
    And EM セッションが自動クローズされる

  # ────────────────────────────────────────────────────────
  # Scenario 5: 監視ループによる品質チェック
  # ────────────────────────────────────────────────────────

  Scenario: orchestrator の自動監視と異常検知
    Given orchestrator が `/loop 3m /orchestrate` で監視状態
    And tmux に "em@exp-stock", "eng@exp-stock-task2058" が稼働中
    When 3 分経過してループが1サイクル実行される
    Then orchestrator が全ペインの内容を capture-pane で取得する
    And "?" が表示されているペインを検出する (Engineer の質問)
    And CLAUDE.md ルール に従い自動回答する
    When Engineer が 10 分以上応答がない状態が続く
    Then orchestrator が timeout を検知する
    And ユーザーに "Engineer が応答しません" と alert を出す
    And 必要に応じて "セッション再起動を提案" する

  # ────────────────────────────────────────────────────────
  # Scenario 6: エラーハンドリングと リカバリー
  # ────────────────────────────────────────────────────────

  Scenario: タスク実行失敗時のリカバリー
    Given Engineer が task_2058 を実行中である
    And task_2058 に dependency blockedBy=[task_2057] が設定されている
    When task_2057 が失敗して completed にならない
    Then task_2058 は blocked のまま pending 状態を保つ
    And orchestrator が報告を待つ
    When EM が task_2057 の再実行を指示する
    And Engineer が task_2057 を修正して completed とする
    Then task_2058 の blocked フラグが解除される
    And task_2058 が in_progress に遷移できるようになる
    And orchestrator がユーザーに "Unblocked: task_2058" を通知する
