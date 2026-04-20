Feature: Task Generation Workflow
  Scenario: Generate and validate tasks from instantiated workflow
    Given a workflow instance created from "Product Launch" template
    And the instance has 3 phases with assigned specialists:
      | Phase Name  | Specialist Email       |
      | Planning    | alice@example.com      |
      | Development | bob@example.com        |
      | Testing     | carol@example.com      |
    When I trigger auto-task generation
    Then tasks should be generated for each phase:
      | Phase Name  | Task Count | Assignee               |
      | Planning    | 1          | alice@example.com      |
      | Development | 1          | bob@example.com        |
      | Testing     | 1          | carol@example.com      |
    And each task should have title, description, and assignee
    And placeholder variables should be resolved in task titles
    And placeholder variables should be resolved in descriptions
    And tasks should respect phase sequential order
    And phase tasks should only become active after previous phase completion
    And all initial tasks should be in "blocked" status
