"""
Tests for KuzuDB template repository.

Covers:
- Template CRUD operations
- Node and edge management
- Cypher query execution
- Sync mechanism (SQLite ↔ KuzuDB)
- Integrity verification
"""

import pytest
import sqlite3
import os
import tempfile
from datetime import datetime

from workflow.repositories.kuzu_connection import KuzuConnection
from workflow.repositories.kuzu_template_repository import KuzuTemplateRepository
from workflow.services.kuzu_schema import KuzuSchema
from workflow.services.template_sync import TemplateSyncManager


@pytest.fixture
def kuzu_memory_conn(tmp_path):
    """Create temporary KuzuDB connection for testing."""
    db_path = str(tmp_path / "test_kuzu.db")
    conn = KuzuConnection(db_path)
    KuzuSchema.create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def sqlite_memory_db():
    """Create in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            category TEXT,
            usage_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE template_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            type TEXT DEFAULT 'task',
            estimated_duration_minutes INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            role_hint TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(template_id, task_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE template_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            from_task_id TEXT NOT NULL,
            to_task_id TEXT NOT NULL,
            edge_type TEXT DEFAULT 'depends_on',
            condition TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    yield conn
    conn.close()


class TestKuzuTemplateRepository:
    """Test KuzuDB template repository operations."""

    def test_save_template_basic(self, kuzu_memory_conn):
        """Test saving a basic template."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        template_data = {
            "template_id": 1,
            "name": "Test Template",
            "description": "A test template",
            "category": "testing",
            "tags": ["test", "demo"],
            "nodes": [
                {
                    "node_id": "task1",
                    "name": "Task 1",
                    "description": "First task",
                    "type": "task",
                    "estimated_duration_minutes": 30,
                    "priority": "high",
                    "role_hint": "engineer"
                }
            ],
            "edges": []
        }

        result = repo.save_template(template_data)
        assert result == 1

    def test_save_template_with_edges(self, kuzu_memory_conn):
        """Test saving a template with nodes and edges."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        template_data = {
            "template_id": 2,
            "name": "DAG Template",
            "description": "Template with DAG structure",
            "category": "workflow",
            "nodes": [
                {
                    "node_id": "task1",
                    "name": "Task 1",
                    "type": "task",
                    "estimated_duration_minutes": 30
                },
                {
                    "node_id": "task2",
                    "name": "Task 2",
                    "type": "task",
                    "estimated_duration_minutes": 45
                }
            ],
            "edges": [
                {
                    "from": "task1",
                    "to": "task2",
                    "type": "depends_on",
                    "confidence_score": 1.0
                }
            ]
        }

        result = repo.save_template(template_data)
        assert result == 2

    def test_get_template(self, kuzu_memory_conn):
        """Test retrieving a template."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        # Save template
        template_data = {
            "template_id": 3,
            "name": "Retrievable Template",
            "description": "Template to retrieve",
            "category": "test",
            "nodes": [
                {
                    "node_id": "node1",
                    "name": "Node 1",
                    "type": "step"
                }
            ],
            "edges": []
        }
        repo.save_template(template_data)

        # Retrieve template
        retrieved = repo.get_template(3)
        assert retrieved is not None
        assert retrieved["template_id"] == 3
        assert retrieved["name"] == "Retrievable Template"
        assert len(retrieved["nodes"]) == 1
        assert retrieved["nodes"][0]["node_name"] == "Node 1"

    def test_get_nonexistent_template(self, kuzu_memory_conn):
        """Test retrieving a nonexistent template."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)
        result = repo.get_template(999)
        assert result is None

    def test_list_templates(self, kuzu_memory_conn):
        """Test listing templates."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        # Save multiple templates
        for i in range(1, 4):
            template_data = {
                "template_id": i,
                "name": f"Template {i}",
                "description": f"Description {i}",
                "category": "test" if i < 3 else "other",
                "nodes": [],
                "edges": []
            }
            repo.save_template(template_data)

        # List all
        templates, total = repo.list_templates()
        assert total == 3
        assert len(templates) == 3

        # List by category
        templates, total = repo.list_templates(category="test")
        assert total == 2

    def test_list_templates_pagination(self, kuzu_memory_conn):
        """Test pagination in list_templates."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        # Save 25 templates
        for i in range(1, 26):
            template_data = {
                "template_id": i,
                "name": f"Template {i}",
                "category": "test",
                "nodes": [],
                "edges": []
            }
            repo.save_template(template_data)

        # Get first page
        page1, total = repo.list_templates(page=1, limit=10)
        assert len(page1) == 10
        assert total == 25

        # Get second page
        page2, total = repo.list_templates(page=2, limit=10)
        assert len(page2) == 10

    def test_update_template(self, kuzu_memory_conn):
        """Test updating template metadata."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        # Save template
        template_data = {
            "template_id": 10,
            "name": "Update Test",
            "description": "Original",
            "category": "test",
            "nodes": [],
            "edges": []
        }
        repo.save_template(template_data)

        # Update
        success = repo.update_template(10, {
            "description": "Updated",
            "usage_count": 5
        })
        assert success is True

        # Verify update
        updated = repo.get_template(10)
        assert updated["description"] == "Updated"
        assert updated["usage_count"] == 5

    def test_delete_template(self, kuzu_memory_conn):
        """Test deleting a template."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        # Save template with nodes
        template_data = {
            "template_id": 11,
            "name": "Delete Test",
            "nodes": [
                {"node_id": "n1", "name": "Node 1"},
                {"node_id": "n2", "name": "Node 2"}
            ],
            "edges": [
                {"from": "n1", "to": "n2"}
            ]
        }
        repo.save_template(template_data)

        # Verify it exists
        assert repo.get_template(11) is not None

        # Delete
        success = repo.delete_template(11)
        assert success is True

        # Verify deletion
        assert repo.get_template(11) is None

    def test_find_templates_by_category(self, kuzu_memory_conn):
        """Test finding templates by category."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        # Save templates in different categories
        for category in ["dev", "dev", "staging", "prod"]:
            template_data = {
                "template_id": hash(f"{category}{datetime.now()}") % 1000,
                "name": f"Template {category}",
                "category": category,
                "nodes": [],
                "edges": []
            }
            repo.save_template(template_data)

        # Find by category
        dev_templates = repo.find_templates_by_category("dev")
        assert len(dev_templates) >= 2

    def test_find_similar_templates(self, kuzu_memory_conn):
        """Test finding similar templates."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        # Save templates with similar structures
        templates = [
            {
                "template_id": 20,
                "name": "5-node template",
                "nodes": [
                    {"node_id": f"n{i}", "name": f"Node {i}"}
                    for i in range(5)
                ],
                "edges": []
            },
            {
                "template_id": 21,
                "name": "4-node template",
                "nodes": [
                    {"node_id": f"n{i}", "name": f"Node {i}"}
                    for i in range(4)
                ],
                "edges": []
            }
        ]

        for t in templates:
            repo.save_template(t)

        # Find similar with low threshold
        similar = repo.find_similar_templates(
            {"node_count": 5, "edge_count": 0},
            threshold=0.5
        )
        # Should find templates similar to 5-node structure
        assert len(similar) >= 1

    def test_get_template_statistics(self, kuzu_memory_conn):
        """Test getting template statistics."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        # Save templates
        for i in range(3):
            template_data = {
                "template_id": 30 + i,
                "name": f"Stat Template {i}",
                "category": "test",
                "nodes": [
                    {"node_id": "n1", "name": "Node 1"},
                    {"node_id": "n2", "name": "Node 2"}
                ],
                "edges": [{"from": "n1", "to": "n2"}]
            }
            repo.save_template(template_data)

        stats = repo.get_template_statistics()
        assert stats["total_templates"] >= 3
        assert stats["total_nodes"] >= 6
        assert stats["total_edges"] >= 3

    def test_record_template_match(self, kuzu_memory_conn):
        """Test recording template match."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        template_data = {
            "template_id": 40,
            "name": "Match Test",
            "nodes": [],
            "edges": []
        }
        repo.save_template(template_data)

        success = repo.record_template_match(
            template_id=40,
            workflow_id=1,
            match_score=0.95,
            match_reason="Structure similarity",
            matched_fields=["category", "type"]
        )
        assert success is True

    def test_get_template_usage_history(self, kuzu_memory_conn):
        """Test getting template usage history."""
        repo = KuzuTemplateRepository(kuzu_memory_conn)

        template_data = {
            "template_id": 50,
            "name": "Usage Test",
            "nodes": [],
            "edges": []
        }
        repo.save_template(template_data)

        # Record some matches
        for _ in range(3):
            repo.record_template_match(50, 1, 0.9, "test")

        history = repo.get_template_usage_history(50)
        assert len(history) == 1
        assert history[0]["usage_count"] == 3


class TestTemplateSyncManager:
    """Test SQLite ↔ KuzuDB synchronization."""

    def test_sync_single_template(self, sqlite_memory_db, kuzu_memory_conn):
        """Test syncing a single template."""
        # Insert into SQLite
        cursor = sqlite_memory_db.cursor()
        cursor.execute(
            "INSERT INTO templates (name, description, category, usage_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("Sync Test", "Test template", "test", 0, datetime.now().isoformat(), datetime.now().isoformat())
        )
        template_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO template_nodes (template_id, task_id, name, description, type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (template_id, "task1", "Task 1", "Test task", "task", datetime.now().isoformat())
        )

        sqlite_memory_db.commit()

        # Sync to KuzuDB
        sync_manager = TemplateSyncManager(sqlite_memory_db, kuzu_memory_conn)
        success = sync_manager.sync_template_to_kuzu(template_id)

        assert success is True

        # Verify in KuzuDB
        repo = KuzuTemplateRepository(kuzu_memory_conn)
        kuzu_template = repo.get_template(template_id)
        assert kuzu_template is not None
        assert kuzu_template["name"] == "Sync Test"

    def test_verify_sync_integrity(self, sqlite_memory_db, kuzu_memory_conn):
        """Test sync integrity verification."""
        cursor = sqlite_memory_db.cursor()

        # Create template in SQLite
        cursor.execute(
            "INSERT INTO templates (name, description, category, usage_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("Integrity Test", "Test", "test", 0, datetime.now().isoformat(), datetime.now().isoformat())
        )
        template_id = cursor.lastrowid

        # Add nodes
        for i in range(3):
            cursor.execute(
                "INSERT INTO template_nodes (template_id, task_id, name, type, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (template_id, f"task{i}", f"Task {i}", "task", datetime.now().isoformat())
            )

        # Add edges
        for i in range(2):
            cursor.execute(
                "INSERT INTO template_edges (template_id, from_task_id, to_task_id, edge_type, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (template_id, f"task{i}", f"task{i+1}", "depends_on", datetime.now().isoformat())
            )

        sqlite_memory_db.commit()

        # Sync
        sync_manager = TemplateSyncManager(sqlite_memory_db, kuzu_memory_conn)
        sync_manager.sync_template_to_kuzu(template_id)

        # Verify integrity
        verified = sync_manager.verify_sync_integrity(template_id)
        assert verified is True

    def test_sync_all_templates(self, sqlite_memory_db, kuzu_memory_conn):
        """Test syncing all templates."""
        cursor = sqlite_memory_db.cursor()

        # Create multiple templates
        for i in range(3):
            cursor.execute(
                "INSERT INTO templates (name, description, category, usage_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f"Template {i}", f"Description {i}", "test", 0, datetime.now().isoformat(), datetime.now().isoformat())
            )

        sqlite_memory_db.commit()

        # Sync all
        sync_manager = TemplateSyncManager(sqlite_memory_db, kuzu_memory_conn)
        stats = sync_manager.sync_all_templates()

        assert stats["total"] == 3
        assert stats["successful"] == 3
        assert stats["failed"] == 0

    def test_get_sync_status(self, sqlite_memory_db, kuzu_memory_conn):
        """Test getting sync status."""
        cursor = sqlite_memory_db.cursor()

        # Add some templates to SQLite
        for i in range(2):
            cursor.execute(
                "INSERT INTO templates (name, description, category, usage_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f"Status Test {i}", "", "test", 0, datetime.now().isoformat(), datetime.now().isoformat())
            )

        sqlite_memory_db.commit()

        sync_manager = TemplateSyncManager(sqlite_memory_db, kuzu_memory_conn)
        status = sync_manager.get_sync_status()

        assert status["sqlite_template_count"] == 2
        assert "kuzu_template_count" in status
        assert "sync_complete" in status


class TestKuzuSchema:
    """Test KuzuDB schema initialization."""

    def test_create_schema(self, kuzu_memory_conn):
        """Test schema creation."""
        # Schema already created in fixture
        verified = KuzuSchema.verify_schema(kuzu_memory_conn)
        assert verified is True

    def test_verify_schema(self, kuzu_memory_conn):
        """Test schema verification."""
        verified = KuzuSchema.verify_schema(kuzu_memory_conn)
        assert verified is True

    def test_drop_schema(self, kuzu_memory_conn):
        """Test schema deletion."""
        KuzuSchema.drop_schema(kuzu_memory_conn)
        verified = KuzuSchema.verify_schema(kuzu_memory_conn)
        assert verified is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
