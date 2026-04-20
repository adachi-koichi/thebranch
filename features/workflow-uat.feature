Feature: Workflow UAT - End-to-End Integration Testing
  As a product manager
  I want to validate the complete workflow system
  So that I can ensure business process automation works reliably in production

  Scenario: Complete workflow execution from template to task completion
    Given a workflow template "QA Release Process" with phases:
      | Phase Name         | Specialist Type | Sequential | Task Count |
      | Requirements       | Product Manager | true       | 2          |
      | Implementation     | Engineer        | true       | 3          |
      | Testing            | QA Engineer     | true       | 2          |
    When I instantiate the template with specialists:
      | Phase Name         | Specialist Email     |
      | Requirements       | pm@company.com       |
      | Implementation     | eng@company.com      |
      | Testing            | qa@company.com       |
    Then a workflow instance is created with 3 phase instances
    And tasks are auto-generated for each phase (2+3+2=7 total)
    And the Requirements phase becomes active first
    And implementation and testing phases are locked until requirements complete

  Scenario: Phase transition with task completion validation
    Given a workflow instance with Requirements phase active
    And the Requirements phase has 2 tasks assigned to pm@company.com
    When all Requirements phase tasks are marked complete
    Then the Requirements phase transitions to COMPLETED state
    And the Implementation phase automatically unlocks
    And notification is sent to eng@company.com
    And phase transition audit log is recorded

  Scenario: Delegation chain verification (orchestrator → EM → Engineer)
    Given an orchestrator initiates a workflow execution request
    When the orchestrator delegates the workflow to Engineering Manager
    Then the EM receives task delegation with full workflow context
    And the EM distributes phase tasks to assigned engineers
    And each engineer receives their phase task assignments
    And delegation chain is logged with timestamps and actor info
    And task assignments reference the delegation chain

  Scenario: Error handling and recovery during phase transition
    Given a workflow instance in Implementation phase
    When an error occurs during task completion (e.g., validation failure)
    Then the task remains in IN_PROGRESS state
    And error details are logged with task context
    And the phase transition is blocked until error is resolved
    When the error is fixed and task is retried
    Then the task completes successfully
    And phase transition proceeds automatically
    And error recovery is logged in audit trail

  Scenario: Specialist auto-assignment based on phase requirements
    Given a workflow template with specialist type requirements
    When instantiating with available specialists
    Then the system matches specialists to phases based on type
    And specialist availability is checked
    And specialist assignment is confirmed and logged
    And assigned specialist receives notification with task details

  Scenario: Concurrent phase monitoring and status aggregation
    Given a multi-phase workflow instance running
    When multiple phases have active tasks simultaneously
    Then workflow status dashboard shows:
      | Phase State    | Task Progress | Assigned Specialist |
      | ACTIVE         | 2/3 tasks     | eng@company.com     |
      | LOCKED         | 0/2 tasks     | qa@company.com      |
      | COMPLETED      | 2/2 tasks     | pm@company.com      |
    And overall workflow progress is calculated correctly
    And phase dependencies are respected

  Scenario: UAT user workflow - Product Manager perspective
    Given I am logged in as a product manager
    When I access the workflow management dashboard
    Then I can:
      | Action                          | Expected Result                    |
      | View all active workflows       | Dashboard shows 3 active workflows |
      | Filter by status                | Can filter PENDING/ACTIVE/COMPLETE |
      | View phase-wise task details    | Expand phase to see 7 total tasks  |
      | Check specialist assignments    | See assigned specialist per phase  |
      | Monitor phase progress          | Real-time progress indicator      |
      | View phase transition timeline  | Timeline shows actual transitions  |

  Scenario: UAT user workflow - Engineer perspective
    Given I am logged in as an engineer
    When I access the task assignment dashboard
    Then I can:
      | Action                          | Expected Result                    |
      | View assigned implementation tasks | 3 Implementation phase tasks shown |
      | Filter by workflow instance     | Can search by workflow name        |
      | Update task status              | Can mark task DONE with comments  |
      | View task dependencies          | See phase dependencies             |
      | Request help/escalation         | Can escalate blocked tasks         |

  Scenario: API endpoint integration - Workflow CRUD operations
    Given the workflow management API is running on port 8000
    When I perform workflow operations:
      | Operation               | Endpoint                | Method | Expected Status |
      | Create workflow         | /api/workflows          | POST   | 201 Created     |
      | Get workflow by ID      | /api/workflows/{id}     | GET    | 200 OK          |
      | List all workflows      | /api/workflows          | GET    | 200 OK          |
      | Update workflow status  | /api/workflows/{id}     | PATCH  | 200 OK          |
      | Delete workflow         | /api/workflows/{id}     | DELETE | 204 No Content  |
    Then all endpoints respond with correct status codes
    And response payloads contain expected fields
    And error handling returns appropriate error messages

  Scenario: API endpoint integration - Phase and Task operations
    Given a workflow instance exists
    When I perform phase/task operations:
      | Operation              | Endpoint                      | Method | Expected Status |
      | Get phases            | /api/workflows/{id}/phases     | GET    | 200 OK          |
      | Get phase tasks       | /api/workflows/{id}/phases/{p}/tasks | GET | 200 OK |
      | Update task status    | /api/workflows/{id}/tasks/{t}  | PATCH  | 200 OK          |
      | Transition phase      | /api/workflows/{id}/phases/{p}/transition | POST | 200 OK |
    Then all operations are properly sequenced
    And task state transitions follow business rules
    And phase transitions validate task completion

  Scenario: Data consistency and transaction integrity
    Given concurrent requests to update workflow state
    When multiple tasks complete simultaneously
    Then:
      | Scenario                        | Expected Behavior              |
      | Concurrent task updates         | Last write wins (no conflicts) |
      | Phase transition during updates | Transaction is atomic          |
      | Notification sends              | Sent once per completion      |
      | Audit log entries               | All state changes are logged  |
      | Database consistency            | No orphaned or duplicate data |
