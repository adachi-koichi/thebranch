Feature: Workflow Template Management
  As a workflow administrator
  I want to create reusable workflow templates
  So that I can instantiate consistent workflows with auto-generated tasks

  Scenario: Create workflow template with phases and task definitions
    Given a workflow template named "Product Launch"
    And the template has description "Standard product launch process"
    And the template defines the following phases:
      | Phase Name      | Specialist Type | Sequential | Task Count |
      | Planning        | Product Manager | true       | 3          |
      | Development     | Engineer        | true       | 5          |
      | Testing         | QA Engineer     | true       | 4          |
      | Deployment      | DevOps          | true       | 2          |
    When I create the workflow template
    Then the template should be stored with ID
    And the template should contain 4 phases in order
    And each phase should have defined task templates

  Scenario: Instantiate template to workflow instance with specialist assignment
    Given a stored workflow template "Product Launch"
    And the template has 4 phases with defined tasks
    And I have assigned specialists:
      | Phase Name      | Assigned Specialist |
      | Planning        | alice@example.com   |
      | Development     | bob@example.com     |
      | Testing         | carol@example.com   |
      | Deployment      | dave@example.com    |
    When I instantiate the template with specialist assignments
    Then a new workflow instance should be created
    And the instance should reference the template
    And the instance should contain 4 phase instances
    And each phase should be assigned to the specified specialist

  Scenario: Auto-generate phase-based tasks from template
    Given a workflow instance created from "Product Launch" template
    And the instance has 4 phases with assigned specialists
    When I trigger auto-task generation
    Then tasks should be generated for each phase:
      | Phase Name      | Task Count | Assignee            |
      | Planning        | 3          | alice@example.com   |
      | Development     | 5          | bob@example.com     |
      | Testing         | 4          | carol@example.com   |
      | Deployment      | 2          | dave@example.com    |
    And each task should have title, description, and assignee
    And tasks should respect phase sequential order
    And phase tasks should only become active after previous phase completion

  Scenario: Reuse existing template and reassign specialists
    Given a stored workflow template "Product Launch"
    And the template has 4 phases with defined tasks
    And I have assigned specialists:
      | Phase Name      | Assigned Specialist |
      | Planning        | alice@example.com   |
      | Development     | bob@example.com     |
      | Testing         | carol@example.com   |
      | Deployment      | dave@example.com    |
    When I reuse the same template with different assignments
    Then a new workflow instance should be created from reused template
    And the reused instance should have new specialist assignments

  Scenario: Validation error when specialist not available
    Given a stored workflow template "Strict Requirements"
    And the template has 3 phases with defined tasks
    And no specialists are registered for type "qa"
    When I attempt to instantiate the template with missing specialist
    Then a validation error should be raised for missing specialist
    And the error should indicate which specialist type is missing

  Scenario: Multiple specialists assigned to same phase
    Given a stored workflow template "Multi-Specialist Template"
    And the template has 2 phases with defined tasks
    And I have assigned specialists:
      | Phase Name  | Assigned Specialist |
      | Planning    | alice@example.com   |
      | Development | bob@example.com     |
    When I instantiate the template with specialist assignments
    Then a new workflow instance should be created
    And the instance should reference the template
    And each phase should be assigned to the specified specialist
