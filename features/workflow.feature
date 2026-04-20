Feature: Complete Workflow Management System - BDD Scenarios
  As a product team member
  I want to manage workflow templates, instantiate them, and track task execution
  So that I can automate complex multi-phase business processes with proper delegation

  Background:
    Given the workflow system is initialized
    And a test specialist directory exists with:
      | Email              | Name            | Specialist Type |
      | pm@company.com     | Project Manager | pm              |
      | eng@company.com    | Lead Engineer   | engineer        |
      | qa@company.com     | QA Engineer     | qa              |

  # ===== TEMPLATE CREATION =====

  Scenario: Create workflow template with sequential phases
    When I create a workflow template named "Development Process"
    And I add phase "Requirements" with specialist type "pm" (sequential)
    And I add phase "Implementation" with specialist type "engineer" (sequential)
    And I add phase "Testing" with specialist type "qa" (sequential)
    Then the template should have 3 phases in order
    And all phases should be marked sequential

  Scenario: Add tasks to template phases
    Given a workflow template named "QA Release"
    When I add 2 tasks to "Requirements" phase
    And I add 3 tasks to "Implementation" phase
    And I add 2 tasks to "Testing" phase
    Then total task definitions should be 7
    And each task should have title, description, priority, and estimated hours

  Scenario: Validate template completeness before instantiation
    Given a workflow template named "Incomplete Process"
    And the template has only 1 phase without any tasks
    When I attempt to validate the template
    Then validation should fail with missing tasks error
    And the template status should remain in "draft"

  # ===== INSTANCE CREATION =====

  Scenario: Instantiate template with specialist assignments
    Given a workflow template named "QA Release Process" with 3 phases and 7 tasks
    When I instantiate the template with specialist assignments:
      | Phase Name         | Assigned Specialist  |
      | Requirements       | pm@company.com       |
      | Implementation     | eng@company.com      |
      | Testing            | qa@company.com       |
    Then a workflow instance should be created
    And instance should reference the original template
    And all 3 phases should be initialized as phase instances

  Scenario: Auto-generate tasks during instantiation
    Given a template instance has just been created
    When the system auto-generates tasks from template definitions
    Then 7 total tasks should be created
    And tasks should be assigned to the phase specialists
    And all generated tasks should start in "blocked" status
    And the first phase tasks should be unblocked

  Scenario: Validate specialist assignment before instantiation
    Given a workflow template with 3 phases
    When I attempt to instantiate with invalid specialist email "invalid@example.com"
    Then instantiation should fail
    And error message should indicate specialist not found

  # ===== PHASE EXECUTION =====

  Scenario: Execute first phase with sequential unlock
    Given a workflow instance with 3 sequential phases
    And the first phase has 2 tasks
    And the second and third phases are locked
    When I complete all tasks in the first phase
    And I mark the first phase as completed
    Then the first phase status should be "completed"
    And the second phase should automatically unlock
    And all second phase tasks should become unblocked
    And the third phase should remain locked

  Scenario: Phase transition with notification
    Given the Requirements phase is active with 2 completed tasks
    When the Requirements phase completes
    Then a phase transition should be logged
    And a notification should be sent to eng@company.com (Implementation specialist)
    And timestamp should be recorded for the transition

  Scenario: Block phase transition on incomplete tasks
    Given Implementation phase with 3 tasks: 2 completed, 1 in_progress
    When I attempt to complete the Implementation phase
    Then phase transition should be blocked
    And error message should list 1 incomplete task
    And phase status should remain "active"

  # ===== TASK GENERATION & ASSIGNMENT =====

  Scenario: Generate development tasks from template tasks
    Given a workflow template with task definitions:
      | Phase         | Task Title                    | Priority | Est Hours |
      | Requirements  | Gather Requirements          | 1        | 4         |
      | Requirements  | Document Specifications      | 2        | 6         |
      | Implementation| Implement Feature A          | 1        | 8         |
      | Implementation| Implement Feature B          | 2        | 8         |
      | Implementation| Code Review                  | 3        | 4         |
      | Testing       | Execute Test Suite           | 1        | 4         |
      | Testing       | Document Results             | 2        | 2         |
    When I instantiate and generate tasks
    Then dev_tasks table should have 7 entries
    And each task should reference the workflow_instance_id
    And each task should have wf_node_key = "{phase_key}_{task_key}"
    And all tasks should have created_at timestamp

  Scenario: Task assignment based on phase specialist
    Given a workflow instance with Requirements phase assigned to pm@company.com
    When tasks are generated for Requirements phase
    Then all Requirements tasks should be assigned to pm@company.com
    And assignee field should contain the specialist email

  Scenario: Task dependency tracking
    Given generated tasks have dependencies:
      | Successor Task            | Depends On                   |
      | Code Review               | Implement Feature A          |
      | Code Review               | Implement Feature B          |
      | Document Results          | Execute Test Suite           |
    When I query task dependencies
    Then task_dependencies table should have 3 entries
    And predecessor_id should reference completed task
    And successor_id should reference dependent task
    And tasks should respect dependency order

  # ===== DELEGATION CHAIN (orchestrator → EM → Engineer) =====

  Scenario: Delegation chain initialization
    Given a workflow instance is created
    When an orchestrator initiates phase execution
    Then the following delegations should occur:
      | Actor         | Action                                      |
      | Orchestrator  | Creates workflow instance                   |
      | Orchestrator  | Delegates to Engineering Manager             |
      | EM            | Receives delegation with task list           |
      | EM            | Distributes tasks to assigned engineers     |
      | Engineer      | Receives individual task assignments        |
    And each delegation should be logged with timestamp
    And each delegation should record delegated_by and delegated_to

  Scenario: Task assignment to engineer in delegation chain
    Given an EM has received phase tasks from orchestrator
    And the EM needs to assign 3 Implementation tasks to an engineer
    When the EM creates an engineer task assignment
    Then a tmux session should be created for the engineer
    And task details should be sent to the engineer's session
    And the engineer should receive the following context:
      | Context Item           |
      | Workflow template name |
      | Phase name             |
      | Task list (3 items)    |
      | Specialist assignment  |
      | Dependencies           |

  Scenario: Engineer task completion tracking
    Given 3 Implementation tasks assigned to eng@company.com
    When the engineer marks a task as completed
    Then the following should occur:
      | Action                         | Expected Result                |
      | Task status → completed        | Task marked with timestamp     |
      | Dependencies checked           | Dependent tasks may unlock     |
      | Notification sent to EM        | EM receives completion update  |
      | Phase progress updated         | Phase shows 1/3 tasks done     |
      | Audit log entry recorded       | Completion logged              |

  # ===== ERROR HANDLING & RECOVERY =====

  Scenario: Recover from validation failure during instantiation
    Given a template with 3 phases and 7 tasks
    When instantiation fails due to missing specialist assignment
    Then the following validation errors should occur:
      | State                    | Expected Behavior              |
      | Instance status          | Remains in draft state         |
      | Phases not created       | wf_instance_nodes not created |
      | Tasks not generated      | No dev_tasks created          |
      | Error logged             | Failure details in logs        |
    When I retry instantiation with valid assignments
    Then the instance should be created successfully

  Scenario: Handle concurrent task completion
    Given 3 Implementation tasks are all in_progress
    When all 3 tasks are marked complete within 1 second
    Then the following concurrent behaviors should occur:
      | Check                          | Result                     |
      | Duplicate task completion      | No duplicate entries       |
      | Phase completion logic         | Fires once per phase       |
      | Notifications sent             | One per task, not duplicated |
      | Database consistency           | No orphaned records        |
      | Transaction atomicity          | All updates succeed or fail |

  Scenario: Rollback on phase transition error
    Given Implementation phase with all tasks completed
    When phase transition to Testing fails due to system error
    Then the following rollback behaviors should occur:
      | Check                       | Result                      |
      | Implementation status       | Remains "active"            |
      | Testing phase               | Remains "locked"            |
      | Error logged with context   | Full traceback recorded     |
      | Transaction rolled back     | No partial updates          |
    When I retry the transition
    Then the phase should transition successfully

  # ===== AUDIT & COMPLIANCE =====

  Scenario: Audit log all state changes
    Given a workflow instance executing through multiple phases
    When the following state changes occur:
      | Action                   |
      | Template instantiated    |
      | Tasks generated          |
      | Phase unlocked           |
      | Task completed           |
      | Phase completed          |
    Then audit_logs should record:
      | Field        | Content                           |
      | timestamp    | ISO 8601 format                   |
      | actor        | Email/agent identifier            |
      | action_type  | INSTANTIATE/GENERATE/UNLOCK/... |
      | entity_type  | workflow/phase/task               |
      | entity_id    | Affected record ID                |
      | change_delta | JSON of before/after state       |

  Scenario: Compliance: no tasks created outside workflow phase
    Given a workflow instance with phases
    When I attempt to create a dev_task without workflow_instance_id
    Then the following database constraints should apply:
      | Check                        | Result                     |
      | Database constraint          | Insert fails (FK required) |
      | Error returned to client     | Clear error message        |
      | No orphaned task created     | Record not inserted        |

  Scenario: Data integrity: cascade delete prevents orphans
    Given a workflow instance with 7 generated tasks
    When the workflow instance is deleted
    Then the following cascading deletes should occur:
      | Table           | Action                     |
      | dev_tasks       | All 7 tasks deleted        |
      | task_dependencies | All relationships deleted |
      | wf_instance_nodes| All phase nodes deleted    |
      | workflow_instances| Instance record deleted   |
    And no orphaned records remain in database

  # ===== STATUS AGGREGATION & MONITORING =====

  Scenario: Aggregate workflow status from phase states
    Given a 3-phase workflow with:
      | Phase           | Status    | Tasks    |
      | Requirements    | completed | 2/2      |
      | Implementation  | active    | 2/3      |
      | Testing         | locked    | 0/2      |
    When I query the workflow status
    Then the following metrics should be returned:
      | Metric                     | Value    |
      | Overall status             | IN_PROGRESS |
      | Total tasks                | 7        |
      | Completed tasks            | 2        |
      | Active tasks               | 2        |
      | Blocked tasks              | 3        |
      | Completion percentage      | 28%      |
      | Next phase ready           | false    |

  Scenario: Monitor phase progress in real-time
    Given Implementation phase with 3 tasks
    When I subscribe to phase progress updates
    Then I should receive updates when:
      | Event                  | Data Sent                    |
      | Task completed         | Phase progress: 1/3, 2/3... |
      | Task status changed    | Updated task state           |
      | Task unlocked          | Task becomes available       |
    And updates should be sent within 1 second

  Scenario: List active workflows with phase breakdown
    Given 3 active workflow instances
    When I query active workflows
    Then response should include:
      | Field                | Content                      |
      | instance_id          | Unique identifier            |
      | instance_name        | Human-readable name          |
      | template_name        | Source template name         |
      | status               | PENDING/ACTIVE/COMPLETED     |
      | phases               | Array of phase details       |
      | current_phase        | Name of active phase         |
      | progress             | Overall completion %         |
      | last_updated         | Timestamp                    |
