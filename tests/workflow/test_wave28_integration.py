"""
Integration tests for Wave28: Workflow Auto-Generation
Tests NLPService, GraphService, TemplateService, and KuzuDB integration
"""

import json
import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from workflow.services.nlp_service import NLPService, validate_dag
from workflow.services.graph_service import GraphService
from workflow.services.template_service import TemplateService
from workflow.models.template import TemplateMetadata, TemplateNotFoundError


@pytest.fixture
def temp_kuzu_db():
    """Temporary KuzuDB path for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "workflow_test.kuzu"
        yield str(db_path)


@pytest.fixture
def temp_sqlite_db():
    """Temporary SQLite database for template service"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "templates_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        yield str(db_path)


@pytest.fixture
def graph_service(temp_kuzu_db):
    """GraphService instance with temporary KuzuDB"""
    svc = GraphService(db_path=temp_kuzu_db)
    yield svc
    svc.close()


@pytest.fixture
def template_service(temp_sqlite_db):
    """TemplateService instance with temporary SQLite database"""
    return TemplateService(db_path=temp_sqlite_db)


@pytest.fixture
def sample_valid_workflow():
    """Sample valid DAG structure"""
    return {
        "workflow": {
            "name": "Sample Workflow",
            "description": "A simple workflow for testing",
            "nodes": [
                {
                    "task_id": "t001",
                    "name": "Initialize Project",
                    "type": "task",
                    "description": "Set up project structure",
                    "estimated_duration_minutes": 30,
                    "priority": "high",
                    "role_hint": "project_lead"
                },
                {
                    "task_id": "t002",
                    "name": "Design Architecture",
                    "type": "task",
                    "description": "Design system architecture",
                    "estimated_duration_minutes": 120,
                    "priority": "high",
                    "role_hint": "architect"
                },
                {
                    "task_id": "t003",
                    "name": "Implement Features",
                    "type": "task",
                    "description": "Develop main features",
                    "estimated_duration_minutes": 480,
                    "priority": "high",
                    "role_hint": "developer"
                },
                {
                    "task_id": "t004",
                    "name": "Testing",
                    "type": "task",
                    "description": "Quality assurance",
                    "estimated_duration_minutes": 240,
                    "priority": "high",
                    "role_hint": "qa_engineer"
                }
            ],
            "edges": [
                {"from": "t001", "to": "t002", "type": "depends_on", "condition": None},
                {"from": "t002", "to": "t003", "type": "depends_on", "condition": None},
                {"from": "t003", "to": "t004", "type": "depends_on", "condition": None}
            ]
        }
    }


@pytest.fixture
def sample_invalid_workflow_cycle():
    """Sample workflow with circular dependency"""
    return {
        "workflow": {
            "name": "Cyclic Workflow",
            "description": "Workflow with cycle",
            "nodes": [
                {
                    "task_id": "t001",
                    "name": "Task A",
                    "type": "task",
                    "description": "Task A",
                    "estimated_duration_minutes": 30,
                    "priority": "medium"
                },
                {
                    "task_id": "t002",
                    "name": "Task B",
                    "type": "task",
                    "description": "Task B",
                    "estimated_duration_minutes": 30,
                    "priority": "medium"
                },
                {
                    "task_id": "t003",
                    "name": "Task C",
                    "type": "task",
                    "description": "Task C",
                    "estimated_duration_minutes": 30,
                    "priority": "medium"
                }
            ],
            "edges": [
                {"from": "t001", "to": "t002", "type": "depends_on"},
                {"from": "t002", "to": "t003", "type": "depends_on"},
                {"from": "t003", "to": "t001", "type": "depends_on"}  # Creates cycle
            ]
        }
    }


class TestGraphServiceIntegration:
    """GraphService integration tests with KuzuDB"""

    def test_process_and_save_valid_workflow(self, graph_service, sample_valid_workflow):
        """Test saving valid workflow DAG to KuzuDB"""
        generation_id = "autogen-20240101-abc123"

        result = graph_service.process_and_save(generation_id, sample_valid_workflow)

        assert result["success"] is True
        assert result["generation_id"] == generation_id
        assert result["nodes_saved"] == 4
        assert result["edges_saved"] == 3
        assert result["validation"]["is_valid"] is True
        assert result["error"] is None

    def test_process_and_save_invalid_dag_with_cycle(self, graph_service, sample_invalid_workflow_cycle):
        """Test that invalid DAG with cycle returns validation error"""
        generation_id = "autogen-20240101-cyclic"

        result = graph_service.process_and_save(generation_id, sample_invalid_workflow_cycle)

        assert result["success"] is False
        assert result["generation_id"] == generation_id
        assert result["nodes_saved"] == 0
        assert result["edges_saved"] == 0
        assert result["validation"]["is_valid"] is False
        assert len(result["validation"]["errors"]) > 0
        assert any(e["type"] == "CIRCULAR_DEPENDENCY" for e in result["validation"]["errors"])

    def test_get_workflow_graph_after_save(self, graph_service, sample_valid_workflow):
        """Test retrieving saved workflow graph by generation_id"""
        generation_id = "autogen-20240101-retrieve"

        # First save
        graph_service.process_and_save(generation_id, sample_valid_workflow)

        # Then retrieve
        result = graph_service.get_workflow_graph(generation_id)

        assert result["success"] is True
        assert result["generation_id"] == generation_id
        assert len(result["tasks"]) == 4
        assert result["error"] is None

        # Verify task data
        task_ids = [t["task_id"] for t in result["tasks"]]
        assert "t001" in task_ids
        assert "t002" in task_ids
        assert "t003" in task_ids
        assert "t004" in task_ids

    def test_delete_workflow(self, graph_service, sample_valid_workflow):
        """Test deleting workflow and verifying empty result"""
        generation_id = "autogen-20240101-delete"

        # Save
        graph_service.process_and_save(generation_id, sample_valid_workflow)

        # Verify saved
        result_before = graph_service.get_workflow_graph(generation_id)
        assert len(result_before["tasks"]) == 4

        # Delete
        deleted = graph_service.delete_workflow(generation_id)
        assert deleted is True

        # Verify deleted
        result_after = graph_service.get_workflow_graph(generation_id)
        assert len(result_after["tasks"]) == 0

    def test_context_manager_usage(self, temp_kuzu_db):
        """Test GraphService as context manager"""
        with GraphService(db_path=temp_kuzu_db) as svc:
            assert svc is not None
            assert hasattr(svc, 'repository')
            assert hasattr(svc, 'process_and_save')

        # After exit, connection should be closed
        # (Just verify no exception on exit)

    def test_process_and_save_empty_workflow_data(self, graph_service):
        """Test handling of missing workflow data"""
        generation_id = "autogen-20240101-empty"
        nlp_result = {"data": {}}

        result = graph_service.process_and_save(generation_id, nlp_result)

        assert result["success"] is False
        assert "No workflow data" in result["error"]

    def test_process_and_save_no_nodes(self, graph_service):
        """Test handling of workflow with no nodes"""
        generation_id = "autogen-20240101-nonodes"
        nlp_result = {
            "workflow": {
                "name": "Empty",
                "nodes": [],
                "edges": []
            }
        }

        result = graph_service.process_and_save(generation_id, nlp_result)

        assert result["success"] is False
        assert result["validation"]["is_valid"] is False


class TestTemplateServiceIntegration:
    """TemplateService integration tests"""

    def test_create_template_basic(self, template_service):
        """Test creating a basic template"""
        nodes = [
            {
                "task_id": "t001",
                "name": "Phase 1",
                "type": "task",
                "estimated_duration_minutes": 60
            }
        ]
        edges = []

        metadata = template_service.create_template(
            name="Test Template",
            description="A test template",
            nodes=nodes,
            edges=edges,
            category="test"
        )

        assert metadata.template_id is not None
        assert metadata.name == "Test Template"
        assert metadata.category == "test"

    def test_get_template(self, template_service):
        """Test retrieving template with nodes and edges"""
        nodes = [
            {
                "task_id": "t001",
                "name": "Task 1",
                "type": "task",
                "description": "First task",
                "estimated_duration_minutes": 30
            },
            {
                "task_id": "t002",
                "name": "Task 2",
                "type": "task",
                "description": "Second task",
                "estimated_duration_minutes": 60
            }
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"}
        ]

        metadata = template_service.create_template(
            name="Template with Edges",
            description="Test edges",
            nodes=nodes,
            edges=edges
        )

        template = template_service.get_template(metadata.template_id)

        assert template["name"] == "Template with Edges"
        assert len(template["nodes"]) == 2
        assert len(template["edges"]) == 1
        assert template["nodes"][0]["task_id"] == "t001"
        assert template["edges"][0]["from_task_id"] == "t001"

    def test_list_templates(self, template_service):
        """Test listing templates"""
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
        assert all(isinstance(t, TemplateMetadata) for t in templates)

    def test_update_template(self, template_service):
        """Test updating template"""
        metadata = template_service.create_template(
            name="Original",
            description="Original description",
            nodes=[{"task_id": "t001", "name": "Task", "type": "task"}]
        )

        updated = template_service.update_template(
            metadata.template_id,
            name="Updated",
            description="Updated description"
        )

        assert updated.name == "Updated"
        assert updated.description == "Updated description"

    def test_delete_template(self, template_service):
        """Test deleting template"""
        metadata = template_service.create_template(
            name="To Delete",
            description="Will be deleted",
            nodes=[{"task_id": "t001", "name": "Task", "type": "task"}]
        )

        result = template_service.delete_template(metadata.template_id)
        assert result is True

        with pytest.raises(TemplateNotFoundError):
            template_service.get_template(metadata.template_id)

    def test_instantiate_template(self, template_service):
        """Test instantiating template to workflow instance"""
        nodes = [
            {
                "task_id": "t001",
                "name": "Phase 1",
                "type": "task",
                "description": "First phase",
                "estimated_duration_minutes": 120,
                "priority": "high"
            }
        ]

        metadata = template_service.create_template(
            name="Instantiate Test",
            description="For instantiation",
            nodes=nodes
        )

        instance = template_service.instantiate_template(metadata.template_id)

        assert instance["generation_id"] is not None
        assert instance["template_id"] == metadata.template_id
        assert instance["workflow"]["name"] == "Instantiate Test"
        assert len(instance["workflow"]["nodes"]) == 1
        assert instance["created_at"] is not None


class TestTemplateAndGraphPipeline:
    """Integration tests for template → graph pipeline"""

    def test_template_to_graph_pipeline(self, template_service, graph_service):
        """Test complete pipeline: create template → instantiate → save to graph"""
        # Step 1: Create template
        nodes = [
            {
                "task_id": "phase_design",
                "name": "Design Phase",
                "type": "task",
                "description": "Design the system",
                "estimated_duration_minutes": 240,
                "priority": "high"
            },
            {
                "task_id": "phase_implement",
                "name": "Implementation Phase",
                "type": "task",
                "description": "Implement features",
                "estimated_duration_minutes": 480,
                "priority": "high"
            },
            {
                "task_id": "phase_test",
                "name": "Testing Phase",
                "type": "task",
                "description": "Test and QA",
                "estimated_duration_minutes": 240,
                "priority": "high"
            }
        ]
        edges = [
            {"from": "phase_design", "to": "phase_implement", "type": "depends_on"},
            {"from": "phase_implement", "to": "phase_test", "type": "depends_on"}
        ]

        metadata = template_service.create_template(
            name="Software Development",
            description="Standard SDLC workflow",
            nodes=nodes,
            edges=edges,
            category="development"
        )

        # Step 2: Instantiate template
        instance = template_service.instantiate_template(metadata.template_id)
        generation_id = instance["generation_id"]

        # Step 3: Save to KuzuDB
        # Wrap workflow in the expected format
        result = graph_service.process_and_save(
            generation_id,
            {"workflow": instance["workflow"]}
        )

        assert result["success"] is True
        assert result["nodes_saved"] == 3
        assert result["edges_saved"] == 2

        # Step 4: Retrieve from KuzuDB
        retrieved = graph_service.get_workflow_graph(generation_id)

        assert retrieved["success"] is True
        assert len(retrieved["tasks"]) == 3
        task_names = [t["name"] for t in retrieved["tasks"]]
        assert "Design Phase" in task_names
        assert "Implementation Phase" in task_names
        assert "Testing Phase" in task_names

    def test_match_template_by_keywords(self, template_service):
        """Test template matching by keywords"""
        # Create templates
        template_service.create_template(
            name="Agile Development",
            description="Sprint-based development workflow with daily standups",
            nodes=[{"task_id": "t001", "name": "Sprint Planning", "type": "task"}]
        )

        template_service.create_template(
            name="Waterfall Development",
            description="Sequential phases for project delivery",
            nodes=[{"task_id": "t001", "name": "Requirements", "type": "task"}]
        )

        # Match by keyword
        matches = template_service.match_by_keywords("daily standup")

        assert len(matches) > 0
        assert any("Agile" in m.name for m in matches)

    def test_match_template_by_structure(self, template_service):
        """Test template matching by structural similarity"""
        # Create template with 3 nodes and 2 edges
        template_service.create_template(
            name="Three-Phase Workflow",
            description="Workflow with 3 phases",
            nodes=[
                {"task_id": "t001", "name": "Phase 1", "type": "task"},
                {"task_id": "t002", "name": "Phase 2", "type": "task"},
                {"task_id": "t003", "name": "Phase 3", "type": "task"}
            ],
            edges=[
                {"from": "t001", "to": "t002", "type": "depends_on"},
                {"from": "t002", "to": "t003", "type": "depends_on"}
            ]
        )

        # Match by similar structure
        matches = template_service.match_by_structure(
            nodes=[{}, {}, {}],  # 3 nodes
            edges=[{}, {}]  # 2 edges
        )

        assert len(matches) > 0

    def test_normalize_template_structure(self, template_service):
        """Test template structure normalization"""
        template_data = {
            "nodes": [
                {"task_id": "t001", "name": "Task 1"},
                {"task_id": "t001", "name": "Task 1 Duplicate"},  # Duplicate
                {"task_id": "t002", "name": "Task 2"}
            ],
            "edges": [
                {"from": "t001", "to": "t002", "type": "depends_on"},
                {"from": "t001", "to": "t001", "type": "depends_on"}  # Self-loop
            ]
        }

        normalized = template_service.normalize_template_structure(template_data)

        # Should have unique nodes only
        assert len(normalized["nodes"]) == 2

        # Should not have self-loops
        assert len(normalized["edges"]) == 1
        assert normalized["edges"][0]["from"] != normalized["edges"][0]["to"]

        # Verify metadata
        assert normalized["metadata"]["is_normalized"] is True
        assert normalized["metadata"]["node_count"] == 2
        assert normalized["metadata"]["edge_count"] == 1


class TestValidationWithGraphService:
    """Integration tests for validation within GraphService"""

    def test_validation_result_includes_warnings(self, graph_service):
        """Test that validation includes warnings for multiple start nodes"""
        workflow_with_multiple_starts = {
            "workflow": {
                "name": "Multiple Starts",
                "nodes": [
                    {"task_id": "t001", "name": "Start 1", "type": "task"},
                    {"task_id": "t002", "name": "Start 2", "type": "task"},
                    {"task_id": "t003", "name": "End", "type": "task"}
                ],
                "edges": [
                    {"from": "t001", "to": "t003", "type": "depends_on"},
                    {"from": "t002", "to": "t003", "type": "depends_on"}
                ]
            }
        }

        result = graph_service.process_and_save("test-multi-start", workflow_with_multiple_starts)

        # Validation passes (no errors) but includes warnings
        assert result["success"] is True
        assert result["validation"]["is_valid"] is True
        assert len(result["validation"]["warnings"]) > 0
        assert any(w["type"] == "MULTIPLE_START_NODES" for w in result["validation"]["warnings"])

    def test_validation_detects_isolated_nodes(self, graph_service):
        """Test validation detects isolated nodes"""
        workflow_with_isolated = {
            "workflow": {
                "name": "Isolated Node",
                "nodes": [
                    {"task_id": "t001", "name": "Start", "type": "task"},
                    {"task_id": "t002", "name": "End", "type": "task"},
                    {"task_id": "t003", "name": "Isolated", "type": "task"}
                ],
                "edges": [
                    {"from": "t001", "to": "t002", "type": "depends_on"}
                ]
            }
        }

        result = graph_service.process_and_save("test-isolated", workflow_with_isolated)

        # Valid DAG but with isolated node warnings
        assert result["success"] is True
        assert result["validation"]["is_valid"] is True
        assert any(w["type"] == "ISOLATED_NODES" for w in result["validation"]["warnings"])
