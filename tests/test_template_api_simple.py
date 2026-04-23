"""
Simple smoke tests for Template API endpoints

These tests verify that the API endpoints are functional and return expected response formats.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from dashboard.app import app


@pytest.fixture(autouse=True)
def cleanup_db():
    """Clean up the test database before each test."""
    db_dir = Path(__file__).parent.parent / "dashboard" / "data"
    db_file = db_dir / "thebranch.sqlite"

    if db_file.exists():
        db_file.unlink()

    yield

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


class TestTemplateAPI:
    """Test Template API endpoints."""

    def test_create_template_returns_201(self, client, auth_header):
        """Test that create template returns 201 Created."""
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Product Launch",
                "description": "New product launch workflow",
                "category": "launch",
                "nodes": [
                    {"task_id": "t001", "name": "Planning", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        assert response.status_code == 201
        assert response.json()["success"] is True
        assert "template_id" in response.json()["data"]

    def test_get_templates_returns_200(self, client, auth_header):
        """Test that list templates returns 200 OK."""
        response = client.get(
            "/api/v1/templates",
            headers=auth_header
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "templates" in response.json()["data"]
        assert "pagination" in response.json()["data"]

    def test_get_template_detail_returns_200(self, client, auth_header):
        """Test that get template detail returns 200 OK."""
        # Create a template first
        create_response = client.post(
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

        template_id = create_response.json()["data"]["template_id"]

        # Get the template
        response = client.get(
            f"/api/v1/templates/{template_id}",
            headers=auth_header
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["data"]["template_id"] == template_id

    def test_match_templates_returns_200(self, client, auth_header):
        """Test that match templates returns 200 OK."""
        # Create a template first
        client.post(
            "/api/v1/templates",
            json={
                "name": "Launch Template",
                "description": "Product launch",
                "nodes": [
                    {"task_id": "t1", "name": "Task", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        response = client.post(
            "/api/v1/templates/match",
            json={
                "natural_language_input": "launch product",
                "auto_match_template": True
            },
            headers=auth_header
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "matched_templates" in response.json()["data"]

    def test_update_template_returns_200(self, client, auth_header):
        """Test that update template returns 200 OK."""
        # Create a template
        create_response = client.post(
            "/api/v1/templates",
            json={
                "name": "Original",
                "description": "Original description",
                "nodes": [
                    {"task_id": "t1", "name": "Task", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        template_id = create_response.json()["data"]["template_id"]

        # Update it
        response = client.put(
            f"/api/v1/templates/{template_id}",
            json={
                "name": "Updated",
                "description": "Updated description"
            },
            headers=auth_header
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_authentication_required(self, client):
        """Test that authentication is required."""
        response = client.get("/api/v1/templates")

        assert response.status_code == 401

    def test_invalid_auth_header_format(self, client):
        """Test that invalid auth header is rejected."""
        response = client.get(
            "/api/v1/templates",
            headers={"Authorization": "InvalidFormat token"}
        )

        assert response.status_code == 401

    def test_template_not_found(self, client, auth_header):
        """Test that getting non-existent template returns 404."""
        response = client.get(
            "/api/v1/templates/99999",
            headers=auth_header
        )

        assert response.status_code == 404

    def test_response_format_has_success_field(self, client, auth_header):
        """Test that all responses have success field."""
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Test",
                "nodes": [
                    {"task_id": "t1", "name": "Task", "type": "task"}
                ],
                "edges": []
            },
            headers=auth_header
        )

        assert "success" in response.json()
        assert "data" in response.json()
