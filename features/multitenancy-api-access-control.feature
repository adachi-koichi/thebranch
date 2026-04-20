Feature: API Access Control and Authorization in Multi-Tenant System
  As an API consumer
  I want to access only authorized endpoints with appropriate permissions
  So that unauthorized access and privilege escalation is prevented

  Background:
    Given the multi-tenant API is running
    And JWT token validation is enabled
    And the following users and roles exist:
      | User ID       | Tenant | Role           | Permissions |
      | alice@tenant  | TENANT-A | admin    | ALL |
      | bob@tenant    | TENANT-A | engineer | READ,WRITE_OWN |
      | carol@tenant  | TENANT-B | viewer   | READ_ONLY |
    And rate limiting is configured as: 1000 req/hour per tenant

  Scenario: Allow authenticated admin to access all endpoints
    Given user alice with admin role is authenticated
    And alice's JWT token is valid
    When alice sends GET request to /api/admin/settings
    Then response status should be 200
    And response contains complete admin settings
    And access is logged with alice's user_id and tenant context

  Scenario: Deny access without valid JWT token
    Given no JWT token is provided in the request
    When an unauthenticated request is sent to /api/workflows
    Then response status should be 401
    And error message "Authentication required" should be returned
    And request should not access any protected resources

  Scenario: Enforce role-based endpoint access
    Given user bob with engineer role is authenticated
    And engineer role does not have admin endpoint permission
    When bob sends request to /api/admin/users
    Then response status should be 403
    And error message "Insufficient permissions" should be returned
    And no user list should be exposed

  Scenario: Validate scope in OAuth token
    Given user carol has read-only scope in JWT
    When carol attempts to POST /api/workflows
    Then response status should be 403
    And error code "SCOPE_MISMATCH" should be returned
    And the POST operation should not execute

  Scenario: Enforce tenant isolation in endpoint access
    Given alice (TENANT-A admin) has valid JWT with tenant_id=TENANT-A
    When alice sends request to /api/workflows with tenant_id=TENANT-B in body
    Then request should be rejected with HTTP 400
    And error "Tenant mismatch with authentication context" should be returned
    And TENANT-B data should not be accessed

  Scenario: Rate limit API requests per tenant
    Given rate limit is 1000 requests per hour for TENANT-A
    When TENANT-A sends 1001 requests in one hour
    Then first 1000 requests should succeed with 200 status
    And 1001st request should be rejected with HTTP 429
    And response header "Retry-After" should be present
    And other tenants should not be affected by the limit

  Scenario: Validate request signature for sensitive operations
    Given user bob initiates DELETE /api/workflows/123
    And sensitive operations require cryptographic signature
    When request does not include valid signature
    Then response status should be 401
    And error "Invalid request signature" should be returned
    And deletion should not proceed

  Scenario: Enforce field-level access control
    Given workflow record contains fields: id, title, data, secret_token
    And bob has READ permission but not READ_SENSITIVE
    When bob requests GET /api/workflows/123
    Then response should include: id, title, data
    And secret_token field should be excluded from response
    And field filtering should be enforced consistently

  Scenario: Prevent privilege escalation through token modification
    Given carol has viewer role token
    When carol modifies JWT payload to change role to "admin"
    Then token signature validation should fail
    And request should be rejected with 401
    And attempted privilege escalation should be logged
    And carol should be notified of the failed attempt

  Scenario: Validate API key format and expiration
    Given API key "sk_live_abc123xyz" for TENANT-A
    And API key expiration date is 2025-12-31
    When API key is used after expiration date
    Then request should be rejected with 401
    And error "API key expired" should be returned
    And access to all protected endpoints should be denied
