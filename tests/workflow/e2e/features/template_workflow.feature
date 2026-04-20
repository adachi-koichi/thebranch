Feature: Template Definition Workflow
  Scenario: Create and publish a workflow template with phases
    Given a new workflow template named "Product Launch"
    And the template has description "Standard product launch process"
    And the template defines the following phases:
      | Phase Name  | Specialist Type | Sequential |
      | Planning    | pm              | true       |
      | Development | engineer        | true       |
      | Testing     | qa              | false      |
    When I create the workflow template
    And I publish the template
    Then the template should be stored with ID
    And the template should contain 3 phases in order
    And each phase should have defined task templates
    And the template status should be "published"
