Feature: Performance and Scalability
  As a platform operator
  I want to ensure workflow system scales efficiently
  So that large-scale deployments with many workflows can operate reliably

  Background:
    Given the workflow system is initialized
    And database performance baseline is established

  Scenario: Handle bulk template creation performance
    Given no templates exist in the system
    When 100 workflow templates are created in batch:
      | Template Name Pattern | Phases | Task Defs | Rate      |
      | Template-{i}          | 5      | 20        | 10/sec    |
    Then all templates should be created successfully
    And creation should complete within 15 seconds
    And database should be indexed for fast queries
    And memory usage should not exceed baseline + 100MB

  Scenario: Optimize query performance for large workflow lists
    Given 1000 workflow instances exist in database
    And templates have 100+ generated tasks each
    When listing all active workflows with pagination
      | Page Size | Sort Field       | Filter                |
      | 50        | created_at DESC  | status = "active"     |
    Then query should complete in under 500ms
    And response should include pagination metadata
    And database should use indexed queries
    And no full table scans should occur

  Scenario: Efficient task generation for large workflows
    Given a workflow template with 50 phases
    And each phase has 20 task definitions
    And 500 total tasks to generate
    When task generation is triggered
    Then all tasks should be generated in under 5 seconds
    And database insertions should use batch operations
    And transaction should remain atomic
    And concurrent task generation should not interfere

  Scenario: Handle concurrent phase transitions efficiently
    Given workflow instance with 10 independent phases
    And all phases have 5 completed tasks
    When all 10 phases attempt simultaneous transition
    Then transitions should serialize properly
    And no race conditions should occur
    And each transition should complete in under 1 second
    And audit log should record all transitions with timestamps

  Scenario: Optimize specialist assignment for large teams
    Given 50 specialists available
    And workflow templates requiring specific specialist types
    And 200 workflow instantiation requests queued
    When instantiation processes assignments in parallel
    Then all assignments should complete correctly
    And specialist availability should be accurately tracked
    And no specialist should be over-assigned
    And response time should scale linearly with specialist count

  Scenario: Cache frequently accessed templates
    Given workflow templates with high access frequency
    When template is accessed 100 times within 1 minute
    Then template should be cached after first access
    And subsequent accesses should return from cache
    And response time should improve by 50%+
    And cache should invalidate on template updates
    And cache size should remain bounded

  Scenario: Partition large task dependency graphs
    Given workflow with 1000 tasks with complex dependencies
    And dependency graph forms directed acyclic graph (DAG)
    When dependency resolution is computed
    Then system should partition graph into logical sections
    And resolution should complete in under 2 seconds
    And memory footprint should not exceed 200MB
    And no infinite loops should be possible

  Scenario: Handle large data exports efficiently
    Given workflow instance with 500 tasks and full history
    And 10000 audit log entries
    When full data export is requested (JSON format)
    Then export should complete in under 10 seconds
    And exported file size should be reasonable (< 50MB)
    And export should not block other operations
    And streaming should be used for large datasets

  Scenario: Monitor and alert on performance degradation
    Given baseline performance metrics established:
      | Metric                    | Baseline | Alert Threshold |
      | Template creation time    | 100ms    | 500ms          |
      | Task generation time      | 50ms/task| 200ms/task     |
      | Query response time       | 100ms    | 500ms          |
      | Database connection pool  | 10       | 5 available    |
    When operations exceed alert thresholds
    Then system should generate performance alert
    And alert should include metric, current value, threshold
    And alert should be logged for analysis
    And operations should continue (not blocked)

  Scenario: Support horizontal scaling with load balancing
    Given workflow system deployed on 3 server nodes
    And load balancer distributing traffic across nodes
    When 1000 concurrent requests are sent
    Then requests should be balanced across servers
    And each server should handle ~333 requests
    And session state should be shared across nodes
    And response times should remain consistent
