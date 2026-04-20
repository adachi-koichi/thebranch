Feature: Workflow Dashboard and User Interface
  As a product manager or engineer
  I want to visualize workflow status and manage workflows through a dashboard
  So that I can monitor progress and make informed decisions

  Background:
    Given the workflow dashboard is deployed at "https://localhost:3000"
    And user is authenticated and logged in
    And multiple active workflows exist

  Scenario: Display workflow list with key metrics
    When user navigates to dashboard home page
    Then workflow list should display:
      | Column              | Content                    |
      | Workflow Name       | Project name               |
      | Status              | PENDING/ACTIVE/COMPLETED   |
      | Progress            | Visual progress bar 0-100% |
      | Current Phase       | Active phase name          |
      | Lead                | Assigned PM name           |
      | Last Updated        | Relative timestamp         |
    And List should be sortable by all columns
    And Default sort should be by "Last Updated DESC"

  Scenario: Filter workflows by status and team
    Given workflows with mixed statuses and teams
    When user applies filters:
      | Filter Type | Value               |
      | Status      | ACTIVE              |
      | Team        | ExpStock Team       |
      | Date Range  | Last 7 days         |
    Then list should update to show only matching workflows
    And Filtered count should be accurate
    And Filter should persist across navigation

  Scenario: View detailed workflow timeline
    Given workflow "Project X" with phase history
    When user clicks on workflow name
    Then detailed view should show timeline:
      | Phase           | Status    | Start Date | End Date     | Duration |
      | Requirements    | COMPLETED | 2024-01-01 | 2024-01-05   | 4 days   |
      | Implementation  | ACTIVE    | 2024-01-05 | (in progress)| 2 days   |
      | Testing         | LOCKED    | TBD        | TBD          | TBD      |
    And Timeline should be visually represented
    And Critical path should be highlighted

  Scenario: Display phase details and task breakdown
    When user clicks on "Implementation" phase
    Then phase details panel should show:
      | Field                | Value                              |
      | Phase Name           | Implementation                     |
      | Status               | ACTIVE                             |
      | Assigned Specialist  | bob@company.com                    |
      | Tasks                | 3 total, 1 complete, 1 in progress |
      | Blocked Tasks        | 0                                  |
      | Est. Completion      | 2024-01-15                         |
    And Task list should be expandable
    And Specialist details should be accessible

  Scenario: Update task status from dashboard
    Given task "Implement Feature A" in PROGRESS state
    When user updates task status to COMPLETED
    And user adds completion comment "Work completed and tested"
    Then task should update in real-time
    And Phase progress should reflect update
    And Completion event should trigger notifications
    And Audit log should record status change with user

  Scenario: Search workflows by keyword
    Given 50+ workflows in system
    When user searches for keyword "stock"
    Then results should include:
      - Workflows with "stock" in name
      - Workflows in "ExpStock Team"
      - Workflows with "stock" in description
    And Results should be ranked by relevance
    And Search should be case-insensitive
    And Result count should be displayed

  Scenario: Export workflow data as CSV/PDF
    Given workflow with 20 tasks and phase history
    When user selects "Export" and chooses format "CSV"
    Then export file should contain:
      - Workflow metadata
      - Phase information
      - Task list with status, assignee, dates
      - Audit log summary
    And File should be downloadable
    And Export should not block other operations

  Scenario: Receive real-time notifications in dashboard
    Given dashboard is open in browser
    When task completes in active workflow
    Then notification should appear in dashboard:
      - Toast message for 5 seconds
      - Task row should highlight briefly
      - Notification should include action link
    And User should be able to dismiss notification
    And Notification should persist in notification center

  Scenario: Compare two workflow timelines
    Given two completed workflows to compare
    When user selects "Compare Workflows"
    Then side-by-side view should display:
      | Metric           | Workflow A | Workflow B | Variance |
      | Total Duration   | 10 days    | 8 days     | -2 days  |
      | Phase Count      | 4          | 4          | -        |
      | Avg Phase Time   | 2.5 days   | 2 days     | -0.5 days|
      | Task Count       | 20         | 18         | -2       |
      | Completion Rate  | 100%       | 100%       | -        |

  Scenario: Download workflow execution report
    Given user requests report for workflow "Project X"
    When user customizes report options:
      | Option        | Selection          |
      | Format        | PDF                |
      | Include       | Tasks, Timeline    |
      | Date Range    | Full execution     |
      | Recipient     | pm@company.com     |
    Then report should be generated
    And Recipient should receive email with attachment
    And Report should be professionally formatted
    And Sensitive data should be redacted if needed

  Scenario: Access API documentation from dashboard
    When user clicks "API Documentation" in settings
    Then documentation should display:
      - Authentication endpoints
      - Workflow CRUD operations
      - Task management endpoints
      - Pagination and filtering examples
      - Error response codes
    And Examples should be in curl, Python, JavaScript
    And Try-it-out feature should allow test requests
    And API keys should be manageable from dashboard

  Scenario: Customize dashboard widgets
    Given default dashboard with 5 widgets
    When user clicks "Customize Dashboard"
    Then user should be able to:
      - Hide/show specific widgets
      - Reorder widgets by drag-and-drop
      - Resize widgets
      - Set widget refresh intervals
    And Customization should be saved per user
    And Changes should apply immediately
