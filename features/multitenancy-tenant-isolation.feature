Feature: Tenant Isolation in Multi-Tenant System
  As a system administrator
  I want to ensure complete isolation between tenants
  So that data leakage and cross-tenant access is prevented

  Background:
    Given the multi-tenant system is initialized
    And the following tenants exist:
      | Tenant ID | Tenant Name      | Status   |
      | TENANT-A  | Acme Corporation | active   |
      | TENANT-B  | Beta Industries  | active   |
      | TENANT-C  | Gamma Ventures   | active   |
    And each tenant has isolated database schema
    And each tenant has isolated cache layer

  Scenario: Prevent direct cross-tenant data query
    Given TENANT-A has 50 workflow records in their schema
    And TENANT-B has 30 workflow records in their schema
    When TENANT-B attempts to query workflows from TENANT-A schema
    Then the query should be rejected
    And error code "TENANT_ISOLATION_VIOLATION" should be returned
    And no TENANT-A data should be leaked

  Scenario: Enforce tenant context in API requests
    Given TENANT-A user "alice@tenant-a.com" is authenticated
    And request header contains tenant_id="TENANT-A"
    When alice performs a GET request to /api/workflows
    Then only TENANT-A workflows should be returned
    And response contains header "X-Tenant-Context: TENANT-A"
    And TENANT-B workflows must not appear in results

  Scenario: Reject requests with missing tenant context
    Given a valid JWT token for user "bob@tenant-b.com"
    And the request is missing the tenant_id header
    When bob sends a request to /api/workflows
    Then the request should be rejected with HTTP 400
    And error message "Missing required tenant context" should be returned

  Scenario: Isolate workflow execution between tenants
    Given TENANT-A workflow instance "wf-a-001" is running
    And TENANT-B workflow instance "wf-b-001" is running
    When TENANT-A workflow completes a phase
    Then TENANT-B workflow should not receive completion notifications
    And TENANT-B workflow state should remain unchanged
    And audit log should record tenant context for each operation

  Scenario: Prevent tenant-scoped secret leakage
    Given TENANT-A has secret "api_key_a" stored in tenant vault
    And TENANT-B has secret "api_key_b" stored in tenant vault
    When TENANT-B user requests access to secrets
    Then only "api_key_b" should be returned
    And "api_key_a" should never be accessible
    And access attempt should be logged with tenant context

  Scenario: Isolate resource quotas per tenant
    Given TENANT-A has quota limit of 100 concurrent workflows
    And TENANT-B has quota limit of 50 concurrent workflows
    When TENANT-A launches 100 workflows
    Then TENANT-A should reach its limit exactly at 100
    And TENANT-B should still be able to launch workflows up to 50
    And quota tracking should be isolated per tenant

  Scenario: Enforce tenant isolation in batch operations
    Given TENANT-A prepares bulk update for 20 records
    And TENANT-B prepares bulk update for 15 records
    When both tenants submit batch operations simultaneously
    Then batch operations should execute independently
    And TENANT-A updates should affect only TENANT-A records
    And TENANT-B updates should affect only TENANT-B records
    And no cross-tenant record modification should occur

  Scenario: Isolate error logs per tenant
    Given TENANT-A workflow encounters an error
    And TENANT-B workflow operates normally
    When error logging occurs
    Then error log should contain "tenant_id: TENANT-A"
    And TENANT-B error logs should not appear in TENANT-A context
    And only TENANT-A users can access TENANT-A error logs

  Scenario: Validate tenant context in database transactions
    Given database connection pool is shared across tenants
    And TENANT-A initiates a transaction
    When transaction context is set to "TENANT-A"
    Then all database queries within transaction must have tenant filter
    And any query missing tenant predicate should fail
    And transaction should commit only TENANT-A scoped changes

  Scenario: Prevent tenant ID spoofing in requests
    Given TENANT-B user "bob@tenant-b.com" is authenticated
    And JWT token contains "tenant_id: TENANT-B"
    When bob attempts to modify header to "tenant_id: TENANT-A"
    Then the modified header should be ignored
    And request should process using authenticated tenant context (TENANT-B)
    And audit log should record spoofing attempt
