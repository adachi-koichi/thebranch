Feature: Advanced Error Handling and Recovery
  As a system administrator
  I want to handle complex error scenarios gracefully
  So that workflow executions can recover from failures automatically

  Background:
    Given the workflow system is initialized
    And a workflow template "Resilience Test" with 3 phases
    And specialists are available for all phases

  Scenario: Recover from database connection failure during task update
    Given a workflow instance in active execution
    And task completion is being processed
    When database connection fails mid-transaction
    Then transaction should be rolled back automatically
    And task status should remain unchanged
    When connection is restored
    And task completion is retried
    Then task should complete successfully
    And no duplicate entries should exist

  Scenario: Handle timeout during long-running phase transition
    Given Implementation phase with 5 tasks
    And all 5 tasks are completed
    When phase transition is triggered with 30-second timeout
    And transition computation exceeds timeout
    Then transition should be interrupted gracefully
    And phase status should remain "active"
    And error log should record timeout details
    When retry is attempted with extended timeout
    Then phase transition should succeed

  Scenario: Validate specialist availability during concurrent operations
    Given a workflow instance with multiple phases
    And specialist "eng@company.com" assigned to Implementation phase
    When the specialist is marked unavailable
    And new task generation is triggered
    Then task generation should proceed with status "blocked_on_specialist"
    And system should log specialist unavailability
    When specialist becomes available again
    Then blocked tasks should automatically unblock

  Scenario: Handle cascade delete with orphaned records detection
    Given a workflow instance with 15 generated tasks
    And task dependencies linking all tasks
    When workflow instance deletion is initiated
    Then pre-deletion check should scan for orphaned records
    And cascade delete should remove all related entities atomically
    And audit log should record deletion chain
    And no orphaned records should remain in database

  Scenario: Manage circular dependency detection and prevention
    Given workflow template with 4 phases
    When attempting to create task dependencies that form a cycle:
      | Task       | Depends On |
      | Task A     | Task B     |
      | Task B     | Task C     |
      | Task C     | Task A     |
    Then system should detect circular dependency
    And operation should be rejected with clear error message
    And database should remain unchanged
    And error log should detail the circular dependency

  Scenario: Handle partial failure in bulk task generation
    Given a workflow instance ready for task generation
    And template defines 10 task definitions across 3 phases
    When task generation begins
    And generation fails on task #7 due to validation error
    Then generated tasks #1-6 should be rolled back automatically
    And instance should remain in "ready" state
    And error message should identify which task definition failed
    When validation is fixed
    And task generation is retried
    Then all 10 tasks should be generated successfully

  Scenario: Detect and prevent race condition in concurrent phase transitions
    Given workflow instance with 2 independent phases
    When both phases attempt transition simultaneously
    And system locks are properly managed
    Then only one phase transition should proceed
    And other phase should receive "locked" status
    And both transitions should be logged with sequence numbers

  Scenario: Handle invalid specialist type assignment
    Given workflow template expecting "senior_engineer" specialist type
    And only "junior_engineer" specialists available
    When instantiation is attempted
    Then system should validate specialist type compatibility
    And instantiation should fail with "specialist_type_mismatch" error
    And instance should not be created

  Scenario: Recover from email notification delivery failure
    Given task completion triggers specialist notification
    And email service is temporarily unavailable
    When notification is sent
    Then email delivery failure should be caught
    And task should still be marked complete
    And notification retry should be queued
    And failure log should record delivery error
    When email service is restored
    Then queued notifications should be resent automatically
