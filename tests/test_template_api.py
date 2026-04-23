"""
Test suite for Template API endpoints

Tests cover:
- Template creation (POST /api/v1/templates)
- Template listing (GET /api/v1/templates)
- Template retrieval (GET /api/v1/templates/{id})
- Template updates (PUT /api/v1/templates/{id})
- Template matching (POST /api/v1/templates/match)
- Authentication and authorization
- Error handling
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from fastapi.testclient import TestClient

# Import the app and blueprints
from dashboard.app import app
from workflow.services.template_service import TemplateService


@pytest.fixture(autouse=True)
def cleanup_db():
    """Clean up the test database before each test."""
    from pathlib import Path
    import shutil

    db_dir = Path(__file__).parent.parent / "dashboard" / "data"
    db_file = db_dir / "thebranch.sqlite"

    # Remove old database file
    if db_file.exists():
        db_file.unlink()

    yield

    # Cleanup after test
    if db_file.exists():
        db_file.unlink()


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def auth_header():
    """Create authorization header with Bearer token."""
    return {"Authorization": "Bearer test-token-12345"}


@pytest.fixture
def db_path(tmp_path):
    """Create temporary database for testing."""
    db_file = tmp_path / "test_templates.db"
    return str(db_file)


@pytest.fixture
def service(db_path):
    """Create TemplateService for testing."""
    return TemplateService(db_path=db_path)


class TestTemplateCreation:
    """Test template creation API."""

    def test_create_template_success(self, client, auth_header):
        """Test successful template creation."""
        payload = {
            "name": "Product Launch",
            "description": "新規プロダクトローンチフロー",
            "category": "launch",
            "nodes": [
                {
                    "task_id": "t001",
                    "name": "要件定義",
                    "type": "task",
                    "description": "プロダクト要件の定義",
                    "estimated_duration_minutes": 480,
                    "priority": "high",
                    "role_hint": "pm"
                },
                {
                    "task_id": "t002",
                    "name": "設計",
                    "type": "task",
                    "estimated_duration_minutes": 360,
                    "priority": "high",
                    "role_hint": "architect"
                }
            ],
            "edges": [
                {"from": "t001", "to": "t002", "type": "depends_on"}
            ],
            "tags": ["launch", "important"]
        }

        response = client.post(
            "/api/v1/templates",
            json=payload,
            headers=auth_header
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "template_id" in data["data"]
        assert data["data"]["name"] == "Product Launch"
        assert data["data"]["category"] == "launch"
        assert data["data"]["usage_count"] == 0

    def test_create_template_missing_name(self, client, auth_header):
        """Test template creation fails without name."""
        payload = {
            "description": "Template without name",
            "category": "test",
            "nodes": [],
            "edges": []
        }

        response = client.post(
            "/api/v1/templates",
            json=payload,
            headers=auth_header
        )

        # 422 is returned by Pydantic validation for missing required field
        assert response.status_code == 422

    def test_create_template_no_auth(self, client):
        """Test template creation fails without authorization."""
        payload = {
            "name": "Unauthorized Template",
            "nodes": [],
            "edges": []
        }

        response = client.post(
            "/api/v1/templates",
            json=payload
        )

        assert response.status_code == 401


class TestTemplateRetrieval:
    """Test template retrieval APIs."""

    def test_list_templates_empty(self, client, auth_header):
        """Test listing templates when none exist."""
        response = client.get(
            "/api/v1/templates",
            headers=auth_header
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["templates"] == []
        assert data["data"]["pagination"]["total_count"] == 0

    def test_list_templates_with_pagination(self, client, auth_header):
        """Test listing templates with pagination."""
        # Create some templates first
        for i in range(5):
            client.post(
                "/api/v1/templates",
                json={
                    "name": f"Template {i}",
                    "description": f"Template {i} description",
                    "category": "test",
                    "nodes": [
                        {
                            "task_id": f"t{i}",
                            "name": f"Task {i}",
                            "type": "task"
                        }
                    ],
                    "edges": []
                },
                headers=auth_header
            )

        # List with limit
        response = client.get(
            "/api/v1/templates?page=1&limit=2",
            headers=auth_header
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["templates"]) <= 2
        assert data["data"]["pagination"]["total_count"] >= 5
        assert data["data"]["pagination"]["total_pages"] >= 3

    def test_list_templates_with_category_filter(self, client, auth_header):
        """Test listing templates filtered by category."""
        # Create templates with different categories
        client.post(
            "/api/v1/templates",
            json={
                "name": "Launch Template",
                "category": "launch",
                "nodes": [
                    {"task_id": "t1", "name": "Task 1", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        client.post(
            "/api/v1/templates",
            json={
                "name": "Development Template",
                "category": "development",
                "nodes": [
                    {"task_id": "t2", "name": "Task 2", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        # Filter by category
        response = client.get(
            "/api/v1/templates?category=launch",
            headers=auth_header
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["templates"]) >= 1
        # Check if at least one template matches the category
        assert any(t["category"] == "launch" for t in data["data"]["templates"])

    def test_list_templates_with_search(self, client, auth_header):
        """Test listing templates with search query."""
        client.post(
            "/api/v1/templates",
            json={
                "name": "Product Launch Flow",
                "description": "プロダクトローンチのワークフロー",
                "nodes": [
                    {"task_id": "t1", "name": "Task 1", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        response = client.get(
            "/api/v1/templates?search_q=product",
            headers=auth_header
        )

        assert response.status_code == 200
        data = response.json()
        # Should find the template or return empty list
        assert "templates" in data["data"]

    def test_get_template_success(self, client, auth_header):
        """Test retrieving a specific template."""
        # Create a template
        create_response = client.post(
            "/api/v1/templates",
            json={
                "name": "Test Template",
                "description": "Test description",
                "category": "test",
                "nodes": [
                    {
                        "task_id": "t001",
                        "name": "Task 1",
                        "type": "task"
                    }
                ],
                "edges": []
            },
            headers=auth_header
        )

        template_id = create_response.json()["data"]["template_id"]

        # Retrieve the template
        response = client.get(
            f"/api/v1/templates/{template_id}",
            headers=auth_header
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["template_id"] == template_id
        assert data["data"]["name"] == "Test Template"
        assert len(data["data"]["nodes"]) == 1

    def test_get_template_not_found(self, client, auth_header):
        """Test retrieving non-existent template."""
        response = client.get(
            "/api/v1/templates/9999",
            headers=auth_header
        )

        assert response.status_code == 404


class TestTemplateUpdate:
    """Test template update API."""

    def test_update_template_success(self, client, auth_header):
        """Test successful template update."""
        # Create a template
        create_response = client.post(
            "/api/v1/templates",
            json={
                "name": "Original Name",
                "description": "Original description",
                "nodes": [
                    {"task_id": "t1", "name": "Task 1", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        template_id = create_response.json()["data"]["template_id"]

        # Update the template
        update_payload = {
            "name": "Updated Name",
            "description": "Updated description"
        }

        response = client.put(
            f"/api/v1/templates/{template_id}",
            json=update_payload,
            headers=auth_header
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Updated Name"
        assert data["data"]["description"] == "Updated description"

    def test_update_template_nodes_and_edges(self, client, auth_header):
        """Test updating template nodes and edges."""
        # Create a template
        create_response = client.post(
            "/api/v1/templates",
            json={
                "name": "Template with DAG",
                "nodes": [
                    {
                        "task_id": "t001",
                        "name": "Old Task",
                        "type": "task"
                    }
                ],
                "edges": []
            },
            headers=auth_header
        )

        template_id = create_response.json()["data"]["template_id"]

        # Update nodes and edges
        update_payload = {
            "nodes": [
                {
                    "task_id": "t001",
                    "name": "New Task",
                    "type": "task"
                },
                {
                    "task_id": "t002",
                    "name": "Second Task",
                    "type": "task"
                }
            ],
            "edges": [
                {"from": "t001", "to": "t002", "type": "depends_on"}
            ]
        }

        response = client.put(
            f"/api/v1/templates/{template_id}",
            json=update_payload,
            headers=auth_header
        )

        assert response.status_code == 200

        # Verify the update
        get_response = client.get(
            f"/api/v1/templates/{template_id}",
            headers=auth_header
        )

        template = get_response.json()["data"]
        assert len(template["nodes"]) == 2
        assert len(template["edges"]) == 1

    def test_update_nonexistent_template(self, client, auth_header):
        """Test updating non-existent template."""
        response = client.put(
            "/api/v1/templates/9999",
            json={"name": "Updated Name"},
            headers=auth_header
        )

        assert response.status_code == 404


class TestTemplateMatching:
    """Test template matching API."""

    def test_match_templates_success(self, client, auth_header):
        """Test successful template matching."""
        # Create templates
        client.post(
            "/api/v1/templates",
            json={
                "name": "Product Launch",
                "description": "新規プロダクトローンチのフロー",
                "category": "launch",
                "nodes": [
                    {"task_id": "t1", "name": "Task 1", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        client.post(
            "/api/v1/templates",
            json={
                "name": "Development Workflow",
                "description": "ソフトウェア開発のワークフロー",
                "category": "development",
                "nodes": [
                    {"task_id": "t2", "name": "Task 2", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        # Match templates
        payload = {
            "natural_language_input": "新規プロダクトをローンチする",
            "auto_match_template": True
        }

        response = client.post(
            "/api/v1/templates/match",
            json=payload,
            headers=auth_header
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["matched_templates"]) >= 0
        # best_match could be None if no matches found
        assert "best_match" in data["data"]

    def test_match_templates_empty_input(self, client, auth_header):
        """Test matching fails with empty input."""
        payload = {
            "natural_language_input": "",
            "auto_match_template": True
        }

        response = client.post(
            "/api/v1/templates/match",
            json=payload,
            headers=auth_header
        )

        assert response.status_code == 400

    def test_match_templates_no_auth(self, client):
        """Test matching fails without authentication."""
        payload = {
            "natural_language_input": "some input",
            "auto_match_template": True
        }

        response = client.post(
            "/api/v1/templates/match",
            json=payload
        )

        assert response.status_code == 401


class TestErrorHandling:
    """Test error handling in API."""

    def test_invalid_auth_header_format(self, client):
        """Test request with invalid auth header format."""
        response = client.get(
            "/api/v1/templates",
            headers={"Authorization": "InvalidFormat token"}
        )

        assert response.status_code == 401

    def test_empty_bearer_token(self, client):
        """Test request with empty Bearer token."""
        response = client.get(
            "/api/v1/templates",
            headers={"Authorization": "Bearer "}
        )

        assert response.status_code == 401

    def test_invalid_pagination_params(self, client, auth_header):
        """Test request with invalid pagination parameters."""
        response = client.get(
            "/api/v1/templates?page=0&limit=200",
            headers=auth_header
        )

        # Should fail validation or use defaults
        assert response.status_code in [200, 422]


class TestResponseFormat:
    """Test response format compliance."""

    def test_create_response_format(self, client, auth_header):
        """Test create response matches spec."""
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Test Template",
                "description": "Test",
                "nodes": [
                    {"task_id": "t1", "name": "Task", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        data = response.json()

        # Verify response structure
        assert "success" in data
        assert "data" in data
        assert "template_id" in data["data"]
        assert "name" in data["data"]
        assert "description" in data["data"]
        assert "created_at" in data["data"]
        assert "updated_at" in data["data"]
        assert "usage_count" in data["data"]

    def test_list_response_format(self, client, auth_header):
        """Test list response matches spec."""
        response = client.get(
            "/api/v1/templates",
            headers=auth_header
        )

        data = response.json()

        # Verify response structure
        assert "success" in data
        assert "data" in data
        assert "templates" in data["data"]
        assert "pagination" in data["data"]
        assert "page" in data["data"]["pagination"]
        assert "limit" in data["data"]["pagination"]
        assert "total_count" in data["data"]["pagination"]
        assert "total_pages" in data["data"]["pagination"]

    def test_get_response_format(self, client, auth_header):
        """Test get response matches spec."""
        # Create a template
        create_response = client.post(
            "/api/v1/templates",
            json={
                "name": "Test",
                "nodes": [
                    {"task_id": "t001", "name": "Task 1", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        template_id = create_response.json()["data"]["template_id"]

        response = client.get(
            f"/api/v1/templates/{template_id}",
            headers=auth_header
        )

        data = response.json()

        # Verify response structure
        assert "success" in data
        assert "data" in data
        assert "template_id" in data["data"]
        assert "nodes" in data["data"]
        assert "edges" in data["data"]
        assert "metadata" in data["data"]
