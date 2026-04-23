"""
Tests for TemplateService and TemplateMatcher.

Tests cover:
- Template CRUD operations
- Keyword matching
- Semantic similarity matching
- Structural pattern matching
- Schema validation
- Normalization
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime

from workflow.services.template_service import TemplateService, TemplateMatcher
from workflow.models.template import (
    TemplateMetadata,
    TemplateMatch,
    TemplateNotFoundError,
    TemplateValidationError,
)


@pytest.fixture
def db_path():
    """Create temporary database for tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def template_service(db_path):
    """Create TemplateService instance."""
    return TemplateService(db_path=db_path)


@pytest.fixture
def sample_nodes():
    """Sample DAG nodes."""
    return [
        {
            "task_id": "t001",
            "name": "要件定義",
            "description": "プロダクト要件確定",
            "type": "task",
            "estimated_duration_minutes": 480,
            "priority": "high",
        },
        {
            "task_id": "t002",
            "name": "設計",
            "description": "技術設計",
            "type": "task",
            "estimated_duration_minutes": 960,
            "priority": "high",
        },
        {
            "task_id": "t003",
            "name": "実装",
            "description": "コード実装",
            "type": "task",
            "estimated_duration_minutes": 2880,
            "priority": "high",
        },
    ]


@pytest.fixture
def sample_edges():
    """Sample DAG edges."""
    return [
        {"from": "t001", "to": "t002", "type": "depends_on"},
        {"from": "t002", "to": "t003", "type": "depends_on"},
    ]


class TestTemplateServiceCRUD:
    """Test CRUD operations."""

    def test_create_template_success(self, template_service, sample_nodes, sample_edges):
        """Test successful template creation."""
        metadata = template_service.create_template(
            name="プロダクトローンチ",
            description="新機能リリースフロー",
            nodes=sample_nodes,
            edges=sample_edges,
            category="product",
        )

        assert metadata.template_id is not None
        assert metadata.name == "プロダクトローンチ"
        assert metadata.category == "product"
        assert metadata.usage_count == 0

    def test_create_template_missing_name(self, template_service, sample_nodes, sample_edges):
        """Test creation fails with missing name."""
        with pytest.raises(TemplateValidationError):
            template_service.create_template(
                name="",
                nodes=sample_nodes,
                edges=sample_edges,
            )

    def test_create_template_invalid_edges(self, template_service, sample_nodes):
        """Test creation fails with invalid edge references."""
        invalid_edges = [
            {"from": "t001", "to": "t999", "type": "depends_on"}  # t999 doesn't exist
        ]
        with pytest.raises(TemplateValidationError):
            template_service.create_template(
                name="Invalid",
                nodes=sample_nodes,
                edges=invalid_edges,
            )

    def test_create_template_with_cycle(self, template_service):
        """Test creation fails with circular dependency."""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t002", "name": "Task 2"},
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t001", "type": "depends_on"},  # Cycle!
        ]
        with pytest.raises(TemplateValidationError):
            template_service.create_template(
                name="Circular",
                nodes=nodes,
                edges=edges,
            )

    def test_get_template(self, template_service, sample_nodes, sample_edges):
        """Test retrieving a template."""
        # Create
        metadata = template_service.create_template(
            name="Test Template",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        # Get
        template = template_service.get_template(metadata.template_id)

        assert template["id"] == metadata.template_id
        assert template["name"] == "Test Template"
        assert len(template["nodes"]) == len(sample_nodes)
        assert len(template["edges"]) == len(sample_edges)

    def test_get_template_not_found(self, template_service):
        """Test getting non-existent template."""
        with pytest.raises(TemplateNotFoundError):
            template_service.get_template(9999)

    def test_list_templates(self, template_service, sample_nodes, sample_edges):
        """Test listing templates."""
        # Create multiple templates
        for i in range(3):
            template_service.create_template(
                name=f"Template {i}",
                category="product",
                nodes=sample_nodes,
                edges=sample_edges,
            )

        # List
        templates = template_service.list_templates(category="product", limit=10)

        assert len(templates) == 3
        assert all(isinstance(t, TemplateMetadata) for t in templates)

    def test_list_templates_with_pagination(self, template_service, sample_nodes, sample_edges):
        """Test pagination."""
        # Create 5 templates
        for i in range(5):
            template_service.create_template(
                name=f"Template {i}",
                category="product",
                nodes=sample_nodes,
                edges=sample_edges,
            )

        # Page 1
        page1 = template_service.list_templates(limit=2, page=1)
        assert len(page1) == 2

        # Page 2
        page2 = template_service.list_templates(limit=2, page=2)
        assert len(page2) == 2

        # Page 3
        page3 = template_service.list_templates(limit=2, page=3)
        assert len(page3) == 1

    def test_update_template(self, template_service, sample_nodes, sample_edges):
        """Test updating template."""
        # Create
        metadata = template_service.create_template(
            name="Original Name",
            description="Original Description",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        # Update
        updated = template_service.update_template(
            metadata.template_id,
            name="Updated Name",
            description="Updated Description",
        )

        assert updated.name == "Updated Name"
        assert updated.description == "Updated Description"

    def test_update_template_not_found(self, template_service):
        """Test updating non-existent template."""
        with pytest.raises(TemplateNotFoundError):
            template_service.update_template(9999, name="New Name")

    def test_delete_template(self, template_service, sample_nodes, sample_edges):
        """Test deleting template."""
        # Create
        metadata = template_service.create_template(
            name="To Delete",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        # Delete
        result = template_service.delete_template(metadata.template_id)
        assert result is True

        # Verify deleted
        with pytest.raises(TemplateNotFoundError):
            template_service.get_template(metadata.template_id)

    def test_delete_template_not_found(self, template_service):
        """Test deleting non-existent template."""
        result = template_service.delete_template(9999)
        assert result is False


class TestTemplateMatching:
    """Test template matching functionality."""

    def test_match_by_keywords(self, template_service, sample_nodes, sample_edges):
        """Test keyword matching."""
        # Create templates
        template_service.create_template(
            name="プロダクトローンチフロー",
            description="新機能をリリースするフロー",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        template_service.create_template(
            name="バグ修正プロセス",
            description="バグの検出と修正のプロセス",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        # Match with exact substring that should be in the template
        matches = template_service.match_by_keywords("プロダクトローンチ")

        assert len(matches) > 0
        assert all(isinstance(m, TemplateMatch) for m in matches)
        # First match should be "プロダクトローンチフロー"
        assert matches[0].name == "プロダクトローンチフロー"

    def test_match_by_semantic_similarity(self, template_service, sample_nodes, sample_edges):
        """Test semantic similarity matching."""
        template_service.create_template(
            name="Release Workflow",
            description="Product launch and release process",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        matches = template_service.match_by_semantic_similarity("release product")

        assert len(matches) > 0
        assert matches[0].name == "Release Workflow"

    def test_match_by_structure(self, template_service, sample_nodes, sample_edges):
        """Test structural pattern matching."""
        # Create template
        template_service.create_template(
            name="3-Task Workflow",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        # Create another with different structure
        template_service.create_template(
            name="2-Task Workflow",
            nodes=sample_nodes[:2],
            edges=[{"from": "t001", "to": "t002", "type": "depends_on"}],
        )

        # Match with 3-task structure
        matches = template_service.match_by_structure(sample_nodes, sample_edges)

        # Should find "3-Task Workflow" as best match
        assert len(matches) > 0
        assert matches[0].name == "3-Task Workflow"

    def test_rank_templates(self, template_service):
        """Test ranking templates."""
        matches = [
            TemplateMatch(template_id=1, name="T1", match_score=0.5, match_reason="test"),
            TemplateMatch(template_id=2, name="T2", match_score=0.8, match_reason="test"),
            TemplateMatch(template_id=3, name="T3", match_score=0.3, match_reason="test"),
        ]

        ranked = template_service.rank_templates(matches)

        assert ranked[0].match_score == 0.8
        assert ranked[1].match_score == 0.5
        assert ranked[2].match_score == 0.3


class TestTemplateMatcher:
    """Test TemplateMatcher coordinator."""

    def test_find_best_match_by_text(self, template_service, sample_nodes, sample_edges):
        """Test finding best match from text query."""
        # Create templates
        template_service.create_template(
            name="プロダクト開発フロー",
            description="新規プロダクトの開発フロー",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        # Create matcher
        matcher = TemplateMatcher(template_service)

        # Find match
        matches = matcher.find_best_match(input_text="プロダクト開発", top_k=5)

        assert len(matches) > 0
        assert all(isinstance(m, TemplateMatch) for m in matches)

    def test_find_best_match_by_structure(self, template_service, sample_nodes, sample_edges):
        """Test finding best match from structure."""
        # Create template
        template_service.create_template(
            name="3-Phase Workflow",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        # Create matcher
        matcher = TemplateMatcher(template_service)

        # Find match
        matches = matcher.find_best_match(nodes=sample_nodes, edges=sample_edges, top_k=5)

        assert len(matches) > 0

    def test_find_best_match_combined(self, template_service, sample_nodes, sample_edges):
        """Test finding best match with combined strategy."""
        # Create template
        template_service.create_template(
            name="プロダクトローンチ",
            description="新機能リリース",
            nodes=sample_nodes,
            edges=sample_edges,
        )

        # Create matcher
        matcher = TemplateMatcher(template_service)

        # Find match with both text and structure
        matches = matcher.find_best_match(
            input_text="プロダクト",
            nodes=sample_nodes,
            edges=sample_edges,
            top_k=5,
        )

        assert len(matches) > 0


class TestValidation:
    """Test validation logic."""

    def test_validate_schema_success(self, template_service, sample_nodes, sample_edges):
        """Test schema validation succeeds."""
        errors = template_service._validate_template_schema(sample_nodes, sample_edges)
        assert len(errors) == 0

    def test_validate_schema_missing_task_id(self, template_service):
        """Test validation fails with missing task_id."""
        bad_nodes = [{"name": "Task 1"}]  # Missing task_id
        errors = template_service._validate_template_schema(bad_nodes, [])
        assert len(errors) > 0

    def test_validate_schema_invalid_edge_reference(self, template_service, sample_nodes):
        """Test validation fails with invalid edge reference."""
        bad_edges = [{"from": "t001", "to": "t999", "type": "depends_on"}]
        errors = template_service._validate_template_schema(sample_nodes, bad_edges)
        assert len(errors) > 0

    def test_has_cycle(self, template_service):
        """Test cycle detection."""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t002", "name": "Task 2"},
            {"task_id": "t003", "name": "Task 3"},
        ]
        edges_with_cycle = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t003", "type": "depends_on"},
            {"from": "t003", "to": "t001", "type": "depends_on"},
        ]

        has_cycle = template_service._has_cycle(nodes, edges_with_cycle)
        assert has_cycle is True

    def test_no_cycle(self, template_service, sample_nodes, sample_edges):
        """Test no cycle when structure is valid."""
        has_cycle = template_service._has_cycle(sample_nodes, sample_edges)
        assert has_cycle is False


class TestNormalization:
    """Test template structure normalization."""

    def test_normalize_removes_self_loops(self, template_service, sample_nodes):
        """Test normalization removes self-loops."""
        edges_with_self_loop = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t002", "type": "depends_on"},  # Self-loop
        ]

        template_data = {"nodes": sample_nodes, "edges": edges_with_self_loop}
        normalized = template_service.normalize_template_structure(template_data)

        # Self-loop should be removed
        assert len(normalized["edges"]) == 1

    def test_normalize_assigns_levels(self, template_service, sample_nodes, sample_edges):
        """Test normalization assigns topological levels."""
        template_data = {"nodes": sample_nodes, "edges": sample_edges}
        normalized = template_service.normalize_template_structure(template_data)

        # Check levels are assigned
        for node in normalized["nodes"]:
            assert "level" in node

        # t001 should have level 0, t002 level 1, t003 level 2
        levels = {n["task_id"]: n["level"] for n in normalized["nodes"]}
        assert levels["t001"] == 0
        assert levels["t002"] <= 1
        assert levels["t003"] >= 1

    def test_normalize_deduplicates_nodes(self, template_service):
        """Test normalization deduplicates nodes."""
        nodes_with_duplicates = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t001", "name": "Task 1 (duplicate)"},  # Same task_id
            {"task_id": "t002", "name": "Task 2"},
        ]
        edges = [{"from": "t001", "to": "t002", "type": "depends_on"}]

        template_data = {"nodes": nodes_with_duplicates, "edges": edges}
        normalized = template_service.normalize_template_structure(template_data)

        # Should have 2 unique nodes (t001 and t002)
        assert len(normalized["nodes"]) == 2
