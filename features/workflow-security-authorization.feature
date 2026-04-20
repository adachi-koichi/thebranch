Feature: Security and Authorization Control
  As a security administrator
  I want to enforce access control and authorization
  So that only authorized users can perform workflow operations

  Background:
    Given the workflow system is initialized with role-based access control
    And the following users exist:
      | Email              | Role                     |
      | admin@company.com  | administrator            |
      | pm@company.com     | product_manager          |
      | eng@company.com    | engineer                 |
      | qa@company.com     | qa_engineer              |

  Scenario: Prevent unauthorized user from creating workflow template
    Given a user "eng@company.com" with role "engineer"
    When the user attempts to create a new workflow template
    Then the operation should be rejected
    And error message should indicate "insufficient_permissions"
    And audit log should record unauthorized attempt
    And template should not be created

  Scenario: Enforce role-based view restrictions on workflow instances
    Given workflow instance "Project X" owned by "pm@company.com"
    And another user "qa@company.com" in different team
    When "qa@company.com" attempts to view "Project X"
    Then the instance should not be visible
    And error should indicate "access_denied"
    And audit log should record access attempt

  Scenario: Allow product manager to delegate tasks only within their team
    Given PM "pm@company.com" managing phase tasks
    And engineers in same team: ["eng1@company.com", "eng2@company.com"]
    And engineers in different team: ["eng3@company.com"]
    When PM attempts to assign tasks:
      | Engineer         | Allowed |
      | eng1@company.com | true    |
      | eng2@company.com | true    |
      | eng3@company.com | false   |
    Then assignments within team should succeed
    And assignment to different team should be blocked

  Scenario: Protect sensitive workflow data with encryption
    Given a workflow instance containing:
      | Field         | Value                              |
      | api_key       | secret-key-12345                   |
      | auth_token    | bearer-token-abcde                 |
      | custom_data   | {"password": "encrypted-value"}   |
    When the instance is stored in database
    Then sensitive fields should be encrypted
    And encryption key should be distinct from database
    And decryption should only work for authorized users

  Scenario: Audit trail for sensitive operations
    Given workflow operations:
      | Operation         | Sensitivity |
      | Create template   | Medium      |
      | Delete instance   | High        |
      | Update task       | Low         |
      | Assign specialist | Medium      |
    When each operation is performed
    Then audit log should record:
      | Field             | Value                  |
      | timestamp         | ISO 8601 format        |
      | user              | Acting user email      |
      | operation         | Operation type         |
      | resource_id       | Affected resource ID   |
      | ip_address        | Request origin         |
      | change_delta      | Before/after snapshot  |

  Scenario: Enforce session timeout for inactive administrators
    Given an administrator logged in with active session
    And session timeout is set to 30 minutes
    When 35 minutes of inactivity pass
    Then session should be automatically invalidated
    And next request should require re-authentication
    And session termination should be logged

  Scenario: Prevent privilege escalation attacks
    Given a regular engineer user
    And an administrator role requiring elevated privileges
    When the engineer attempts to:
      | Exploit Vector             |
      | Modify JWT tokens          |
      | Craft admin API calls      |
      | Change role in URL params  |
    Then all attempts should be rejected
    And invalid operations should be logged
    And security alert should be triggered if repeated

  Scenario: Validate API key rotation and revocation
    Given an active API key "api-key-old-12345"
    And new API key "api-key-new-67890"
    When API key rotation is performed
    Then old API key should be deactivated immediately
    And new API key should be active
    And requests with old key should fail with "unauthorized"
    And rotation event should be logged with timestamp

  Scenario: Enforce data retention and purge policies
    Given workflows older than 1 year in database
    And compliance requirement to purge old data
    When data purge job is executed
    Then workflows older than retention period should be deleted
    And audit log of purged records should be preserved
    And dependent records should be cleaned up
    And deletion should be irreversible (not soft-delete)
