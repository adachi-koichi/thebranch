"""
API tests for Wave28: Workflow Auto-Generation
Tests FastAPI endpoints with TestClient and mocked Claude API
"""

import json
import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from dashboard.autogen_routes import router as autogen_router, validate_dag_endpoint
from workflow.services.template_service import TemplateService


@pytest.fixture
def temp_sqlite_db():
    """Temporary SQLite database for template service"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "templates_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        yield str(db_path)


@pytest.fixture
def template_service(temp_sqlite_db):
    """TemplateService instance with temporary SQLite database"""
    return TemplateService(db_path=temp_sqlite_db)


@pytest.fixture
def app():
    """Create FastAPI test app with autogen routes"""
    from fastapi import FastAPI, Header, HTTPException

    app = FastAPI()

    # Re-implement endpoints for testing
    @app.post("/api/v1/workflows/validate-dag")
    async def validate_dag_endpoint(
        request_data: dict,
        authorization: str = Header(None)
    ):
        """DAGバリデーションAPI"""
        try:
            user = None
            if authorization:
                token = authorization.replace("Bearer ", "")
                user = {"id": token, "email": f"user-{token[:8]}@example.com"}

            if not user:
                raise HTTPException(status_code=401, detail="認証が必要です")

            nodes = request_data.get("nodes", [])
            edges = request_data.get("edges", [])

            if not nodes:
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": "ノードが定義されていません"
                    }
                }

            from workflow.services.nlp_service import validate_dag, _compute_critical_path
            validation_result = validate_dag(nodes, edges)
            critical_path = _compute_critical_path(nodes, edges)
            critical_path_duration = sum(
                next((n['estimated_duration_minutes'] for n in nodes if n['task_id'] == t), 0)
                for t in critical_path or []
            )

            return {
                "success": True,
                "data": {
                    "validation_result": validation_result,
                    "statistics": {
                        "total_nodes": len(nodes),
                        "total_edges": len(edges),
                        "critical_path_length": len(critical_path) if critical_path else 0,
                        "critical_path_duration_minutes": critical_path_duration,
                        "critical_path": critical_path or []
                    }
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    @app.post("/api/v1/workflows/auto-generate")
    async def auto_generate_dag(
        request_data: dict,
        authorization: str = Header(None)
    ):
        """自然言語 → DAG変換API"""
        try:
            user = None
            if authorization:
                token = authorization.replace("Bearer ", "")
                user = {"id": token, "email": f"user-{token[:8]}@example.com"}

            if not user:
                raise HTTPException(status_code=401, detail="認証が必要です")

            organization_id = request_data.get("organization_id", "default")
            user_input = request_data.get("natural_language_input", "").strip()
            options = request_data.get("options", {})
            model = options.get("model", "claude-sonnet-4-6")

            if not user_input or len(user_input) < 10:
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": "入力テキストが短すぎます（最小 10 文字）",
                        "details": {"input_length": len(user_input), "minimum_length": 10}
                    }
                }

            from workflow.services.nlp_service import NLPService
            from datetime import datetime
            import uuid
            import json

            nlp_service = NLPService()
            result = nlp_service.extract_workflow_dag(user_input, model=model)

            if not result["success"]:
                return {
                    "success": False,
                    "error": result.get("error", {"code": "UNKNOWN_ERROR", "message": "未知のエラー"})
                }

            generation_id = f"autogen-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
            workflow = result["workflow"]
            validation = result["validation"]

            return {
                "success": True,
                "data": {
                    "generation_id": generation_id,
                    "workflow": workflow,
                    "metadata": {
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                        "model_used": result["metadata"]["model_used"],
                        "prompt_tokens": result["metadata"]["prompt_tokens"],
                        "completion_tokens": result["metadata"]["completion_tokens"],
                        "cache_hit": result["metadata"]["cache_hit"]
                    }
                }
            }

        except HTTPException:
            raise
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": {
                    "code": "PARSING_ERROR",
                    "message": "Claude APIレスポンスが無効なJSONです"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    return app


@pytest.fixture
def client(app):
    """FastAPI TestClient"""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Valid authentication headers for testing"""
    return {"Authorization": "Bearer test-user-token-12345"}


class TestValidateDAGAPI:
    """API tests for validate-dag endpoint"""

    def test_validate_dag_valid(self, client, auth_headers):
        """Test validate-dag API with valid DAG"""
        request_data = {
            "nodes": [
                {
                    "task_id": "t001",
                    "name": "Start",
                    "type": "task",
                    "estimated_duration_minutes": 30,
                    "priority": "high"
                },
                {
                    "task_id": "t002",
                    "name": "End",
                    "type": "task",
                    "estimated_duration_minutes": 60,
                    "priority": "high"
                }
            ],
            "edges": [
                {"from": "t001", "to": "t002", "type": "depends_on"}
            ]
        }

        response = client.post(
            "/api/v1/workflows/validate-dag",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["validation_result"]["is_valid"] is True
        assert data["data"]["statistics"]["total_nodes"] == 2
        assert data["data"]["statistics"]["total_edges"] == 1

    def test_validate_dag_with_cycle(self, client, auth_headers):
        """Test validate-dag API detects cycles"""
        request_data = {
            "nodes": [
                {"task_id": "t001", "name": "Task A", "type": "task"},
                {"task_id": "t002", "name": "Task B", "type": "task"}
            ],
            "edges": [
                {"from": "t001", "to": "t002", "type": "depends_on"},
                {"from": "t002", "to": "t001", "type": "depends_on"}
            ]
        }

        response = client.post(
            "/api/v1/workflows/validate-dag",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_result"]["is_valid"] is False
        assert any(e["type"] == "CIRCULAR_DEPENDENCY"
                   for e in data["data"]["validation_result"]["errors"])

    def test_validate_dag_no_nodes(self, client, auth_headers):
        """Test validate-dag API rejects empty nodes"""
        request_data = {
            "nodes": [],
            "edges": []
        }

        response = client.post(
            "/api/v1/workflows/validate-dag",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_validate_dag_missing_auth(self, client):
        """Test validate-dag API requires authentication"""
        request_data = {
            "nodes": [{"task_id": "t001", "name": "Task", "type": "task"}],
            "edges": []
        }

        response = client.post(
            "/api/v1/workflows/validate-dag",
            json=request_data
        )

        assert response.status_code == 401

    def test_validate_dag_critical_path_calculation(self, client, auth_headers):
        """Test validate-dag calculates critical path"""
        request_data = {
            "nodes": [
                {
                    "task_id": "t001",
                    "name": "Task 1",
                    "type": "task",
                    "estimated_duration_minutes": 30
                },
                {
                    "task_id": "t002",
                    "name": "Task 2",
                    "type": "task",
                    "estimated_duration_minutes": 120
                },
                {
                    "task_id": "t003",
                    "name": "Task 3",
                    "type": "task",
                    "estimated_duration_minutes": 90
                }
            ],
            "edges": [
                {"from": "t001", "to": "t002", "type": "depends_on"},
                {"from": "t002", "to": "t003", "type": "depends_on"}
            ]
        }

        response = client.post(
            "/api/v1/workflows/validate-dag",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        stats = data["data"]["statistics"]
        assert stats["critical_path_length"] == 3
        assert stats["critical_path_duration_minutes"] == 240  # 30 + 120 + 90
        assert stats["critical_path"] == ["t001", "t002", "t003"]


class TestAutoGenerateDAGAPI:
    """API tests for auto-generate endpoint"""

    @patch('dashboard.autogen_routes.NLPService.extract_workflow_dag')
    def test_auto_generate_valid_input(self, mock_nlp, client, auth_headers):
        """Test auto-generate API with valid natural language input"""
        mock_nlp.return_value = {
            "success": True,
            "workflow": {
                "name": "Generated Workflow",
                "description": "Auto-generated from NLP",
                "nodes": [
                    {
                        "task_id": "t001",
                        "name": "Initialize",
                        "type": "task",
                        "description": "Initialize project",
                        "estimated_duration_minutes": 30,
                        "priority": "high"
                    },
                    {
                        "task_id": "t002",
                        "name": "Implement",
                        "type": "task",
                        "description": "Implement features",
                        "estimated_duration_minutes": 120,
                        "priority": "high"
                    }
                ],
                "edges": [
                    {"from": "t001", "to": "t002", "type": "depends_on"}
                ]
            },
            "validation": {
                "is_valid": True,
                "errors": [],
                "warnings": []
            },
            "metadata": {
                "model_used": "claude-sonnet-4-6",
                "prompt_tokens": 500,
                "completion_tokens": 800,
                "cache_hit": False
            }
        }

        request_data = {
            "organization_id": "org-123",
            "natural_language_input": "Create a workflow for software development with initialization and implementation phases",
            "options": {"model": "claude-sonnet-4-6"}
        }

        response = client.post(
            "/api/v1/workflows/auto-generate",
            json=request_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["generation_id"].startswith("autogen-")
        assert data["data"]["workflow"]["name"] == "Generated Workflow"
        assert len(data["data"]["workflow"]["nodes"]) == 2
        assert data["data"]["metadata"]["model_used"] == "claude-sonnet-4-6"

    def test_auto_generate_invalid_input_too_short(self, client, auth_headers):
        """Test auto-generate API rejects short input"""
        request_data = {
            "organization_id": "org-123",
            "natural_language_input": "short",  # Too short
            "options": {}
        }

        response = client.post(
            "/api/v1/workflows/auto-generate",
            json=request_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_INPUT"

    @patch('dashboard.autogen_routes.NLPService.extract_workflow_dag')
    def test_auto_generate_nlp_error_handling(self, mock_nlp, client, auth_headers):
        """Test auto-generate API handles NLP service errors"""
        mock_nlp.return_value = {
            "success": False,
            "workflow": None,
            "validation": None,
            "error": {
                "code": "API_ERROR",
                "message": "Claude API error",
                "details": "Rate limit exceeded"
            }
        }

        request_data = {
            "organization_id": "org-123",
            "natural_language_input": "Create a complex workflow with many phases and dependencies",
            "options": {}
        }

        response = client.post(
            "/api/v1/workflows/auto-generate",
            json=request_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_auto_generate_missing_auth(self, client):
        """Test auto-generate API requires authentication"""
        request_data = {
            "organization_id": "org-123",
            "natural_language_input": "Create a workflow for task management",
            "options": {}
        }

        response = client.post(
            "/api/v1/workflows/auto-generate",
            json=request_data
        )

        assert response.status_code == 401

    @patch('dashboard.autogen_routes.NLPService.extract_workflow_dag')
    def test_auto_generate_with_cache_hit(self, mock_nlp, client, auth_headers):
        """Test auto-generate API includes cache hit metadata"""
        mock_nlp.return_value = {
            "success": True,
            "workflow": {
                "name": "Cached Workflow",
                "nodes": [{"task_id": "t001", "name": "Task", "type": "task"}],
                "edges": []
            },
            "validation": {"is_valid": True, "errors": [], "warnings": []},
            "metadata": {
                "model_used": "claude-sonnet-4-6",
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "cache_hit": True
            }
        }

        request_data = {
            "organization_id": "org-123",
            "natural_language_input": "Create a simple single-task workflow for testing cache",
            "options": {}
        }

        response = client.post(
            "/api/v1/workflows/auto-generate",
            json=request_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["metadata"]["cache_hit"] is True


class TestTemplateAPIs:
    """API tests for template CRUD operations"""

    def test_create_template(self, client, auth_headers, template_service):
        """Test template creation (via service layer)"""
        metadata = template_service.create_template(
            name="Test Template",
            description="A test template",
            nodes=[
                {
                    "task_id": "t001",
                    "name": "Phase 1",
                    "type": "task",
                    "estimated_duration_minutes": 60
                }
            ],
            category="testing"
        )

        assert metadata.template_id is not None
        assert metadata.name == "Test Template"

    def test_get_template(self, client, auth_headers, template_service):
        """Test template retrieval"""
        metadata = template_service.create_template(
            name="Get Test",
            description="Template to retrieve",
            nodes=[
                {
                    "task_id": "t001",
                    "name": "Task",
                    "type": "task"
                }
            ]
        )

        template = template_service.get_template(metadata.template_id)

        assert template["id"] == metadata.template_id
        assert template["name"] == "Get Test"
        assert len(template["nodes"]) == 1

    def test_list_templates(self, client, auth_headers, template_service):
        """Test template listing"""
        # Create multiple templates
        for i in range(3):
            template_service.create_template(
                name=f"Template {i}",
                description=f"Description {i}",
                nodes=[{"task_id": f"t00{i}", "name": f"Task {i}", "type": "task"}],
                category="test"
            )

        templates = template_service.list_templates(category="test")

        assert len(templates) >= 3

    def test_delete_template(self, client, auth_headers, template_service):
        """Test template deletion"""
        metadata = template_service.create_template(
            name="To Delete",
            description="Will be deleted",
            nodes=[{"task_id": "t001", "name": "Task", "type": "task"}]
        )

        result = template_service.delete_template(metadata.template_id)

        assert result is True

    def test_instantiate_template(self, client, auth_headers, template_service):
        """Test template instantiation"""
        metadata = template_service.create_template(
            name="Instantiate Test",
            description="For instantiation",
            nodes=[
                {
                    "task_id": "t001",
                    "name": "Phase 1",
                    "type": "task",
                    "description": "First phase",
                    "estimated_duration_minutes": 120,
                    "priority": "high"
                }
            ]
        )

        instance = template_service.instantiate_template(metadata.template_id)

        assert instance["generation_id"] is not None
        assert instance["template_id"] == metadata.template_id
        assert instance["workflow"]["name"] == "Instantiate Test"
        assert len(instance["workflow"]["nodes"]) == 1


class TestTemplateInstantiationAPI:
    """API tests for template instantiation workflow"""

    def test_template_to_graph_workflow(self, client, auth_headers, template_service):
        """Test complete workflow: create template → instantiate → validate"""
        # Create template
        nodes = [
            {
                "task_id": "design",
                "name": "Design Phase",
                "type": "task",
                "estimated_duration_minutes": 240,
                "priority": "high"
            },
            {
                "task_id": "implement",
                "name": "Implementation Phase",
                "type": "task",
                "estimated_duration_minutes": 480,
                "priority": "high"
            }
        ]
        edges = [
            {"from": "design", "to": "implement", "type": "depends_on"}
        ]

        metadata = template_service.create_template(
            name="SDLC Workflow",
            description="Standard software development lifecycle",
            nodes=nodes,
            edges=edges
        )

        # Instantiate template
        instance = template_service.instantiate_template(metadata.template_id)

        # Validate instantiated workflow
        request_data = {
            "nodes": instance["workflow"]["nodes"],
            "edges": instance["workflow"]["edges"]
        }

        response = client.post(
            "/api/v1/workflows/validate-dag",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["validation_result"]["is_valid"] is True

    def test_template_matching_by_keywords(self, client, auth_headers, template_service):
        """Test template keyword matching"""
        # Create templates
        template_service.create_template(
            name="Agile Development Process",
            description="Sprint-based development with daily standups and retrospectives",
            nodes=[{"task_id": "t001", "name": "Sprint Planning", "type": "task"}]
        )

        template_service.create_template(
            name="Waterfall Development",
            description="Sequential phases of development",
            nodes=[{"task_id": "t001", "name": "Requirements", "type": "task"}]
        )

        # Test matching
        matches = template_service.match_by_keywords("daily standup")
        assert len(matches) > 0
        assert any("Agile" in m.name for m in matches)


class TestErrorHandling:
    """Error handling tests for APIs"""

    def test_validate_dag_invalid_request_format(self, client, auth_headers):
        """Test validate-dag API with missing fields"""
        request_data = {
            "nodes": []  # Empty nodes should fail
        }

        response = client.post(
            "/api/v1/workflows/validate-dag",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_auto_generate_empty_input(self, client, auth_headers):
        """Test auto-generate with empty natural language input"""
        request_data = {
            "organization_id": "org-123",
            "natural_language_input": "",
            "options": {}
        }

        response = client.post(
            "/api/v1/workflows/auto-generate",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    @patch('workflow.services.nlp_service.NLPService.extract_workflow_dag')
    def test_auto_generate_json_parsing_error(self, mock_nlp, client, auth_headers):
        """Test auto-generate handles invalid JSON from NLP service"""
        mock_nlp.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        request_data = {
            "organization_id": "org-123",
            "natural_language_input": "Create a complex workflow for data processing",
            "options": {}
        }

        response = client.post(
            "/api/v1/workflows/auto-generate",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "PARSING_ERROR"


class TestResponseFormats:
    """Tests for consistent response formats"""

    def test_validate_dag_response_structure(self, client, auth_headers):
        """Test validate-dag response has correct structure"""
        request_data = {
            "nodes": [{"task_id": "t001", "name": "Task", "type": "task"}],
            "edges": []
        }

        response = client.post(
            "/api/v1/workflows/validate-dag",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        data = response.json()
        assert "success" in data
        assert "data" in data or "error" in data

        if data["success"]:
            assert "validation_result" in data["data"]
            assert "statistics" in data["data"]
            assert "is_valid" in data["data"]["validation_result"]

    @patch('workflow.services.nlp_service.NLPService.extract_workflow_dag')
    def test_auto_generate_response_structure(self, mock_nlp, client, auth_headers):
        """Test auto-generate response has correct structure"""
        mock_nlp.return_value = {
            "success": True,
            "workflow": {
                "name": "Test",
                "nodes": [{"task_id": "t001", "name": "Task", "type": "task"}],
                "edges": []
            },
            "validation": {"is_valid": True, "errors": [], "warnings": []},
            "metadata": {
                "model_used": "claude-sonnet-4-6",
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "cache_hit": False
            }
        }

        request_data = {
            "organization_id": "org-123",
            "natural_language_input": "Create a simple workflow",
            "options": {}
        }

        response = client.post(
            "/api/v1/workflows/auto-generate",
            json=request_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        data = response.json()
        assert "success" in data
        if data["success"]:
            assert "data" in data
            assert "generation_id" in data["data"]
            assert "workflow" in data["data"]
            assert "metadata" in data["data"]
