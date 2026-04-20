Feature: Instance Instantiation Workflow
  Scenario: Instantiate template with specialist assignments
    Given a stored workflow template "Product Launch" with 3 phases
    And the following specialists are available:
      | Name        | Email              | Specialist Type |
      | Alice       | alice@example.com  | pm              |
      | Bob         | bob@example.com    | engineer        |
      | Carol       | carol@example.com  | qa              |
    And I have assigned specialists:
      | Phase Name  | Assigned Specialist     |
      | Planning    | alice@example.com       |
      | Development | bob@example.com         |
      | Testing     | carol@example.com       |
    When I instantiate the template with specialist assignments
    Then a new workflow instance should be created
    And the instance should reference the template
    And the instance should contain 3 phase instances
    And each phase should be assigned to the specified specialist
    And the instance status should be "ready"

  Scenario: Instantiate with missing specialist validation
    Given a stored workflow template "Product Launch"
    And the template is published
    And no specialists are registered for type "pm"
    When I attempt to instantiate the template
    Then a validation error should be raised
    And the error should indicate missing specialist
