Feature: Multi-Team Orchestration and Isolation
  As an orchestrator managing multiple teams
  I want to orchestrate workflow execution across teams
  So that different teams can work independently without interference

  Background:
    Given the workflow system is initialized with multi-tenancy support
    And the following teams exist:
      | Team Name      | Lead        | Members                          |
      | ExpStock Team  | alice@co.com| alice@, bob@, carol@             |
      | Cancer Research| dave@co.com | dave@, eve@, frank@              |
      | LineStamp Team | grace@co.com| grace@, hank@, ivy@              |

  Scenario: Orchestrate independent workflow execution across teams
    Given 3 workflow templates, one per team
    When orchestrator initiates workflows for all teams simultaneously
    Then each team should have independent workflow instance
    And team data should be completely isolated
    And team1 operations should not affect team2 data
    And team3 completion should not block team1 or team2

  Scenario: Prevent cross-team data access
    Given workflow instances for "ExpStock" and "Cancer" teams
    When ExpStock team member attempts to view Cancer team workflows
    Then access should be denied with "team_isolation_violation"
    And attempt should be logged as unauthorized
    And Cancer team data should not be leaked

  Scenario: Coordinate resource allocation across teams
    Given 10 senior engineers available in pool
    And ExpStock team needs 5 engineers
    And Cancer team needs 6 engineers (exceeds pool)
    When resource allocation is processed
    Then ExpStock should get 5 engineers first (older request)
    And Cancer team should be queued for remaining engineers
    And Queue position should be recorded with timestamp
    And notification should inform Cancer team of wait

  Scenario: Manage team-specific workflow templates
    Given Team-specific templates:
      | Team           | Template Name           | Phases |
      | ExpStock       | Stock Analysis Process  | 4      |
      | Cancer Research| Research Workflow       | 5      |
    When each team instantiates their template
    Then ExpStock should only access Stock Analysis template
    And Cancer should only access Research template
    And Cross-team template access should fail

  Scenario: Handle overlapping specialist assignments across teams
    Given specialist "senior_eng@co.com" available to both teams
    And both teams need to assign the specialist simultaneously
    When both assignment requests arrive
    Then first assignment should succeed
    And second assignment should receive "specialist_unavailable"
    And specialist should appear unavailable for duration
    And assignments should be time-stamped for audit trail

  Scenario: Aggregate dashboards without cross-team leakage
    Given metrics from all 3 teams
    When orchestrator accesses aggregate dashboard
    Then total workflow count should be shown (no breakdown per team)
    And performance metrics should be aggregated
    And sensitive team-specific data should not be visible
    And only high-level summary should be displayed

  Scenario: Team-aware audit logging
    Given operations by all teams
    When audit log is queried
    Then each audit entry should be tagged with team_id
    And team members should only see their own logs
    And orchestrator should see all logs with team context
    And cross-team log access should be prevented

  Scenario: Enforce team-specific SLAs
    Given team SLA definitions:
      | Team           | Phase Timeout | Overall Timeout |
      | ExpStock       | 2 days        | 1 week          |
      | Cancer Research| 3 days        | 2 weeks         |
    When workflows execute beyond team SLA
    Then system should track SLA compliance per team
    And SLA breaches should trigger team-specific alerts
    And Reporting should be team-isolated
    And Cross-team comparisons should not be possible

  Scenario: Support team member escalation chain
    Given team hierarchy:
      | Team           | Lead        | BackupLead  | Escalation |
      | ExpStock       | alice@co.com| bob@co.com  | ceo@co.com |
      | Cancer         | dave@co.com | eve@co.com  | ceo@co.com |
    When critical issue occurs in team
    Then escalation should follow team chain
    And neighboring teams should not be notified automatically
    And Only relevant team's escalation chain should be triggered

  Scenario: Rollback team-specific workflows independently
    Given both teams have active workflows
    And ExpStock team workflow encounters critical error
    When rollback is initiated for ExpStock
    Then ExpStock workflow should rollback to last checkpoint
    And Cancer team workflow should continue unaffected
    And Rollback should not impact other team's database state

  Scenario: Handle team member access removal
    Given bob@co.com is member of ExpStock team
    And bob is assigned to active workflow task
    When bob's access is revoked
    Then bob should not access any ExpStock workflows
    And Active task assignment should be reassigned to alice@co.com
    And Historical records should preserve bob's contribution
    And Access removal should be logged

  Scenario: Support team migration across organizational structure
    Given ExpStock team under Project X organization
    And organizational restructure moves team to Project Y
    When team migration is performed
    Then all historical workflows should follow team
    And Data should be re-partitioned correctly
    And Team members should maintain access
    And Audit trail should record migration event
