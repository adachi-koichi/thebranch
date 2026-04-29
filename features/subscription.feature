# Task #2548: Subscription Management BDD Tests
Feature: Subscription Management
  Scenario: User views available plans
    When user accesses GET /api/subscriptions/plans
    Then response status is 200
    And response contains plans with id "free" and "pro"
    And each plan has required fields: id, name, price_jpy, features

  Scenario: User views their current subscription
    Given user is authenticated
    When user accesses GET /api/subscriptions/current
    Then response status is 200
    And response contains user's current plan

  Scenario: User upgrades from Free to Pro
    Given user is authenticated with "free" plan
    When user sends PATCH /api/subscriptions/plan with {"plan": "pro"}
    Then response status is 200
    And response contains "pro" plan
    And current_period_end is 30 days from now

  Scenario: User cannot change to same plan
    Given user is authenticated with "pro" plan
    When user sends PATCH /api/subscriptions/plan with {"plan": "pro"}
    Then response status is 400
    And error message contains "already on pro plan"

  Scenario: Invalid plan value returns 400 error
    Given user is authenticated
    When user sends PATCH /api/subscriptions/plan with {"plan": "invalid_plan"}
    Then response status is 400
    And error message contains "Invalid plan"

  Scenario: Unauthenticated user cannot view current subscription
    When unauthenticated user accesses GET /api/subscriptions/current
    Then response status is 401
    And error message contains "Not authenticated"

  Scenario: Unauthenticated user cannot change plan
    When unauthenticated user sends PATCH /api/subscriptions/plan with {"plan": "pro"}
    Then response status is 401
    And error message contains "Not authenticated"

  Scenario: Free plan has limited features
    When user accesses GET /api/subscriptions/plans
    Then free plan has max_agents <= 3
    And free plan has api_calls_per_month <= 1000
    And free plan has storage_gb <= 1

  Scenario: Pro plan has more features than Free plan
    When user accesses GET /api/subscriptions/plans
    Then pro plan has max_agents > free plan max_agents
    And pro plan has api_calls_per_month > free plan api_calls_per_month
    And pro plan has storage_gb > free plan storage_gb
    And pro plan price_jpy > free plan price_jpy
