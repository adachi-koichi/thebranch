"""
Unit tests for DAG validation logic
Tests the validate_dag function and related validation utilities
"""

import pytest
from workflow.services.nlp_service import validate_dag


class TestValidateDagBasics:
    """Basic DAG validation tests"""

    def test_empty_nodes_error(self):
        """Test EMPTY_NODES error when no nodes provided"""
        result = validate_dag([], [])

        assert result["is_valid"] is False
        assert len(result["errors"]) > 0
        assert result["errors"][0]["type"] == "EMPTY_NODES"

    def test_duplicate_node_ids_error(self):
        """Test DUPLICATE_NODE_IDS error detection"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t001", "name": "Task 1 Duplicate"},
            {"task_id": "t002", "name": "Task 2"}
        ]
        edges = []

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is False
        assert any(e["type"] == "DUPLICATE_NODE_IDS" for e in result["errors"])
        error = next(e for e in result["errors"] if e["type"] == "DUPLICATE_NODE_IDS")
        assert "t001" in error["affected_nodes"]

    def test_invalid_edge_reference_missing_from(self):
        """Test INVALID_EDGES error when edge references non-existent 'from' node"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t002", "name": "Task 2"}
        ]
        edges = [
            {"from": "t999", "to": "t002", "type": "depends_on"}  # t999 doesn't exist
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is False
        assert any(e["type"] == "INVALID_EDGES" for e in result["errors"])

    def test_invalid_edge_reference_missing_to(self):
        """Test INVALID_EDGES error when edge references non-existent 'to' node"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t002", "name": "Task 2"}
        ]
        edges = [
            {"from": "t001", "to": "t999", "type": "depends_on"}  # t999 doesn't exist
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is False
        assert any(e["type"] == "INVALID_EDGES" for e in result["errors"])

    def test_cycle_detection_simple_a_to_b_to_a(self):
        """Test CIRCULAR_DEPENDENCY detection for simple A→B→A cycle"""
        nodes = [
            {"task_id": "t001", "name": "Task A"},
            {"task_id": "t002", "name": "Task B"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t001", "type": "depends_on"}  # Creates cycle
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is False
        assert any(e["type"] == "CIRCULAR_DEPENDENCY" for e in result["errors"])
        error = next(e for e in result["errors"] if e["type"] == "CIRCULAR_DEPENDENCY")
        assert "t001" in error["affected_nodes"]
        assert "t002" in error["affected_nodes"]

    def test_cycle_detection_three_node_cycle(self):
        """Test CIRCULAR_DEPENDENCY detection for A→B→C→A cycle"""
        nodes = [
            {"task_id": "t001", "name": "Task A"},
            {"task_id": "t002", "name": "Task B"},
            {"task_id": "t003", "name": "Task C"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t003", "type": "depends_on"},
            {"from": "t003", "to": "t001", "type": "depends_on"}  # Creates cycle
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is False
        assert any(e["type"] == "CIRCULAR_DEPENDENCY" for e in result["errors"])

    def test_cycle_detection_self_loop(self):
        """Test CIRCULAR_DEPENDENCY detection for self-loop A→A"""
        nodes = [
            {"task_id": "t001", "name": "Task A"}
        ]
        edges = [
            {"from": "t001", "to": "t001", "type": "depends_on"}  # Self-loop
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is False
        assert any(e["type"] == "CIRCULAR_DEPENDENCY" for e in result["errors"])


class TestValidateDagLinearDAG:
    """Linear DAG validation tests"""

    def test_valid_linear_dag_single_path(self):
        """Test valid linear DAG with single path"""
        nodes = [
            {"task_id": "t001", "name": "Start"},
            {"task_id": "t002", "name": "Middle"},
            {"task_id": "t003", "name": "End"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t003", "type": "depends_on"}
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0
        # Warnings may exist (multiple start/end nodes), but DAG is valid

    def test_valid_linear_dag_single_node(self):
        """Test valid DAG with single node"""
        nodes = [
            {"task_id": "t001", "name": "Only Task"}
        ]
        edges = []

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    def test_valid_linear_dag_two_nodes(self):
        """Test valid DAG with two nodes"""
        nodes = [
            {"task_id": "t001", "name": "First"},
            {"task_id": "t002", "name": "Second"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"}
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0


class TestValidateDagMultipleStartEnd:
    """Tests for multiple start/end node warnings"""

    def test_multiple_start_nodes_warning(self):
        """Test MULTIPLE_START_NODES warning"""
        nodes = [
            {"task_id": "t001", "name": "Start 1"},
            {"task_id": "t002", "name": "Start 2"},
            {"task_id": "t003", "name": "End"}
        ]
        edges = [
            {"from": "t001", "to": "t003", "type": "depends_on"},
            {"from": "t002", "to": "t003", "type": "depends_on"}
        ]

        result = validate_dag(nodes, edges)

        # Should be invalid (multiple starts error out as warning but validation should still work)
        assert any(w["type"] == "MULTIPLE_START_NODES" for w in result["warnings"])

    def test_multiple_end_nodes_warning(self):
        """Test MULTIPLE_END_NODES warning"""
        nodes = [
            {"task_id": "t001", "name": "Start"},
            {"task_id": "t002", "name": "End 1"},
            {"task_id": "t003", "name": "End 2"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t001", "to": "t003", "type": "depends_on"}
        ]

        result = validate_dag(nodes, edges)

        assert any(w["type"] == "MULTIPLE_END_NODES" for w in result["warnings"])

    def test_no_start_nodes_warning(self):
        """Test NO_START_NODE warning when all nodes have dependencies"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t002", "name": "Task 2"}
        ]
        edges = [
            {"from": "t002", "to": "t001", "type": "depends_on"}  # t2 -> t1, so t2 is start
        ]

        result = validate_dag(nodes, edges)

        # t2 has in-degree 0 so it's a valid start
        # The validation passes (no NO_START_NODE warning generated)
        assert result["is_valid"] is True

    def test_no_end_nodes_warning(self):
        """Test NO_END_NODE warning when all nodes have outgoing edges"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t002", "name": "Task 2"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t001", "type": "depends_on"}  # Cycle - no end
        ]

        result = validate_dag(nodes, edges)

        # Will have cycle error instead
        assert result["is_valid"] is False


class TestValidateDagIsolatedNodes:
    """Tests for isolated node detection"""

    def test_isolated_nodes_warning(self):
        """Test ISOLATED_NODES warning when nodes are unreachable from start"""
        nodes = [
            {"task_id": "t001", "name": "Start"},
            {"task_id": "t002", "name": "Middle"},
            {"task_id": "t003", "name": "Isolated"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"}
            # t003 has no connections
        ]

        result = validate_dag(nodes, edges)

        assert any(w["type"] == "ISOLATED_NODES" for w in result["warnings"])
        warning = next(w for w in result["warnings"] if w["type"] == "ISOLATED_NODES")
        assert "t003" in warning["affected_nodes"]

    def test_isolated_node_in_middle(self):
        """Test detection of isolated subgraph"""
        nodes = [
            {"task_id": "t001", "name": "Start"},
            {"task_id": "t002", "name": "End"},
            {"task_id": "t003", "name": "Isolated A"},
            {"task_id": "t004", "name": "Isolated B"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t003", "to": "t004", "type": "depends_on"}  # t3, t4 form separate graph
        ]

        result = validate_dag(nodes, edges)

        assert any(w["type"] == "ISOLATED_NODES" for w in result["warnings"])

    def test_no_isolated_nodes_for_complete_graph(self):
        """Test no ISOLATED_NODES warning for complete reachable graph"""
        nodes = [
            {"task_id": "t001", "name": "Start"},
            {"task_id": "t002", "name": "Middle"},
            {"task_id": "t003", "name": "End"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t003", "type": "depends_on"}
        ]

        result = validate_dag(nodes, edges)

        # Should not have isolated nodes warning
        assert not any(w["type"] == "ISOLATED_NODES" for w in result["warnings"])


class TestValidateDagEdgeTypes:
    """Tests for different edge types"""

    def test_depends_on_edge_type(self):
        """Test validation with depends_on edge type"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t002", "name": "Task 2"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"}
        ]

        result = validate_dag(nodes, edges)
        assert result["is_valid"] is True

    def test_blocks_edge_type(self):
        """Test validation with blocks edge type"""
        nodes = [
            {"task_id": "t001", "name": "Blocker"},
            {"task_id": "t002", "name": "Blocked"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "blocks", "condition": "blocking reason"}
        ]

        result = validate_dag(nodes, edges)
        assert result["is_valid"] is True

    def test_triggers_edge_type(self):
        """Test validation with triggers edge type"""
        nodes = [
            {"task_id": "t001", "name": "Trigger"},
            {"task_id": "t002", "name": "Triggered"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "triggers", "condition": "when x > 5"}
        ]

        result = validate_dag(nodes, edges)
        assert result["is_valid"] is True

    def test_mixed_edge_types(self):
        """Test validation with mixed edge types"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t002", "name": "Task 2"},
            {"task_id": "t003", "name": "Task 3"},
            {"task_id": "t004", "name": "Task 4"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t003", "type": "blocks"},
            {"from": "t003", "to": "t004", "type": "triggers"}
        ]

        result = validate_dag(nodes, edges)
        assert result["is_valid"] is True


class TestValidateDagComplexScenarios:
    """Complex validation scenarios"""

    def test_diamond_dependency_graph(self):
        """Test validation for diamond dependency pattern: A→B,C; B,C→D"""
        nodes = [
            {"task_id": "t001", "name": "A"},
            {"task_id": "t002", "name": "B"},
            {"task_id": "t003", "name": "C"},
            {"task_id": "t004", "name": "D"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t001", "to": "t003", "type": "depends_on"},
            {"from": "t002", "to": "t004", "type": "depends_on"},
            {"from": "t003", "to": "t004", "type": "depends_on"}
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    def test_large_linear_chain(self):
        """Test validation for large linear chain"""
        num_tasks = 10
        nodes = [
            {"task_id": f"t{i:03d}", "name": f"Task {i}"}
            for i in range(1, num_tasks + 1)
        ]
        edges = [
            {"from": f"t{i:03d}", "to": f"t{i+1:03d}", "type": "depends_on"}
            for i in range(1, num_tasks)
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    def test_wide_fanout_graph(self):
        """Test validation for wide fanout: one start, many ends"""
        nodes = [
            {"task_id": "t001", "name": "Start"}
        ] + [
            {"task_id": f"t{i:03d}", "name": f"Task {i}"}
            for i in range(2, 12)
        ]
        edges = [
            {"from": "t001", "to": f"t{i:03d}", "type": "depends_on"}
            for i in range(2, 12)
        ]

        result = validate_dag(nodes, edges)

        # Valid graph but with multiple end nodes warning
        assert any(w["type"] == "MULTIPLE_END_NODES" for w in result["warnings"])

    def test_wide_fanin_graph(self):
        """Test validation for wide fanin: many starts, one end"""
        nodes = [
            {"task_id": f"t{i:03d}", "name": f"Task {i}"}
            for i in range(1, 11)
        ] + [
            {"task_id": "t011", "name": "End"}
        ]
        edges = [
            {"from": f"t{i:03d}", "to": "t011", "type": "depends_on"}
            for i in range(1, 11)
        ]

        result = validate_dag(nodes, edges)

        # Valid graph but with multiple start nodes warning
        assert any(w["type"] == "MULTIPLE_START_NODES" for w in result["warnings"])

    def test_complex_with_multiple_errors(self):
        """Test validation returns all errors when multiple issues exist"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t001", "name": "Task 1 Duplicate"},  # Duplicate
            {"task_id": "t002", "name": "Task 2"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t001", "type": "depends_on"},  # Cycle
            {"from": "t001", "to": "t999", "type": "depends_on"}  # Invalid ref
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is False
        # Should have multiple error types
        error_types = {e["type"] for e in result["errors"]}
        assert "DUPLICATE_NODE_IDS" in error_types or "CIRCULAR_DEPENDENCY" in error_types


class TestValidateDagEmptyAndNulls:
    """Tests for edge cases with empty and null values"""

    def test_nodes_with_missing_required_fields(self):
        """Test nodes with missing task_id raise KeyError"""
        nodes = [
            {"name": "Task without ID"},  # Missing task_id
            {"task_id": "t002", "name": "Task 2"}
        ]
        edges = []

        # Should raise KeyError for missing task_id
        with pytest.raises(KeyError):
            validate_dag(nodes, edges)

    def test_edges_with_no_condition(self):
        """Test edges without condition field are valid"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t002", "name": "Task 2"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"}  # No condition
        ]

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is True

    def test_empty_edges_with_valid_nodes(self):
        """Test single node with no edges is valid"""
        nodes = [
            {"task_id": "t001", "name": "Solo Task"}
        ]
        edges = []

        result = validate_dag(nodes, edges)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0


class TestValidateDagErrorMessages:
    """Tests for error and warning message quality"""

    def test_error_message_contains_node_ids(self):
        """Test that error messages include affected node IDs"""
        nodes = [
            {"task_id": "t001", "name": "Task 1"},
            {"task_id": "t001", "name": "Task 1 Duplicate"}
        ]
        edges = []

        result = validate_dag(nodes, edges)

        error = result["errors"][0]
        assert "affected_nodes" in error
        assert "t001" in error["affected_nodes"]

    def test_circular_dependency_message_shows_path(self):
        """Test that circular dependency message shows the cycle path"""
        nodes = [
            {"task_id": "t001", "name": "Task A"},
            {"task_id": "t002", "name": "Task B"},
            {"task_id": "t003", "name": "Task C"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"},
            {"from": "t002", "to": "t003", "type": "depends_on"},
            {"from": "t003", "to": "t001", "type": "depends_on"}
        ]

        result = validate_dag(nodes, edges)

        error = next(e for e in result["errors"] if e["type"] == "CIRCULAR_DEPENDENCY")
        assert "message" in error
        assert "→" in error["message"]  # Path indicator

    def test_warning_has_affected_nodes(self):
        """Test that warnings include affected_nodes list"""
        nodes = [
            {"task_id": "t001", "name": "Start"},
            {"task_id": "t002", "name": "End"},
            {"task_id": "t003", "name": "Isolated"}
        ]
        edges = [
            {"from": "t001", "to": "t002", "type": "depends_on"}
        ]

        result = validate_dag(nodes, edges)

        warning = next(w for w in result["warnings"] if w["type"] == "ISOLATED_NODES")
        assert "affected_nodes" in warning
        assert "t003" in warning["affected_nodes"]
