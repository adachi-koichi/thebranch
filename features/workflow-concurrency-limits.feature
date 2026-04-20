Feature: Multiagent Concurrency Control (Task #2197)
  Enforce and monitor concurrent session/pane limits for multiagent orchestration.
  Prevent deadlocks and ensure stable resource management through automatic validation.

  Scenario: Enforce orchestrator session limit (max 1)
    Given orchestrator session "ai-orchestrator@main" exists
    And orchestrator window:0 has 1 pane
    When validate_concurrency_limit() is called
    Then orchestrator status is "OK"
    And violations list is empty

  Scenario: Detect orchestrator session multi-launch violation
    Given tmux session "ai-orchestrator@main" exists
    And tmux session "ai-orchestrator@main-2" exists (violation)
    When validate_concurrency_limit() is called
    Then orchestrator status is "VIOLATION"
    And violations contains "orchestrator_multi_session"
    And violation details mention "orchestrator セッション多重起動"

  Scenario: Enforce managers window pane limit (max 2)
    Given session "exp-stock_orchestrator_wf001_feature-x@main" exists
    And managers window has 2 panes (at limit)
    When validate_concurrency_limit() is called
    Then managers status is "OK"
    And violations list is empty

  Scenario: Detect managers window pane limit exceeded (max 2)
    Given session "exp-stock_orchestrator_wf001_feature-x@main" exists
    And managers window has 3 panes (violation)
    When validate_concurrency_limit() is called
    Then managers status is "VIOLATION"
    And violations contains "managers_exceeded"
    And violation details mention "managers ウィンドウペイン数超過"

  Scenario: Enforce members window pane limit (max 3)
    Given session "exp-stock_orchestrator_wf001_feature-x@main" exists
    And members window has 3 panes (at limit)
    When validate_concurrency_limit() is called
    Then members status is "OK"
    And violations list is empty

  Scenario: Detect members window pane limit exceeded (max 3)
    Given session "exp-stock_orchestrator_wf001_feature-x@main" exists
    And members window has 4 panes (violation)
    When validate_concurrency_limit() is called
    Then members status is "EXCEEDED"
    And violations contains "members_exceeded"
    And violation details mention "members ウィンドウペイン数超過"

  Scenario: Block pane creation on engineer limit exceeded
    Given session "exp-stock_orchestrator_wf001_feature-x@main" exists
    And members window already has 3 panes (engineer at max)
    And role is "engineer"
    When start_pane.py attempts to create 4th pane
    Then RuntimeError is raised
    And error message contains "同時起動数制限超過"
    And error message contains "待機キュー登録機能は別タスク"

  Scenario: Multiple team sessions within concurrency limits
    Given session "exp-stock_orchestrator_wf001_feature-x@main" exists with members=3
    And session "breast-cancer_orchestrator_wf002_model@main" exists with members=2
    And session "line-stamp_orchestrator_wf003_ui@main" exists with members=1
    When validate_concurrency_limit() is called
    Then all 3 sessions are within limits
    And violations list is empty
    And all session status values are "OK"

  Scenario: Monitor concurrency in orchestrate_loop.py
    Given orchestrate_loop.py run_once() is executing
    And concurrency violations exist (managers window has 3 panes)
    When Step 0.7 concurrency check executes
    Then violations are logged to ALERTS_LOG
    And logger records "[CONCURRENCY]" warning message
    And results["concurrency_violations"] contains violation entry

  Scenario: Auto-detect deadlock through stale in_progress task
    Given task #100 is in_progress for 120+ minutes
    And corresponding pane has no output for 120+ minutes
    When orchestrate_loop.py detects stale pane
    Then task is marked as blocked
    And auto_recovery.py suggests pane restart
    And deadlock alert is logged
