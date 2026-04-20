"""Tests for KuzuDB GraphRepository for departments"""
import pytest
import sqlite3
import tempfile
from pathlib import Path
from workflow.repositories.kuzu_connection import KuzuConnection
from workflow.repositories.graph_repository_departments import GraphRepositoryDepartments


@pytest.fixture
def kuzu_db():
    """Create in-memory KuzuDB"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / 'test.kuzu')
        conn = KuzuConnection(db_path)
        yield conn
        conn.close()


@pytest.fixture
def sqlite_db():
    """Create in-memory SQLite with schema"""
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # Create agents table
    cursor.execute('''
        CREATE TABLE agents (
            id INTEGER PRIMARY KEY,
            name TEXT,
            slug TEXT UNIQUE,
            role_type TEXT,
            status TEXT
        )
    ''')

    # Create departments and related tables
    cursor.execute('''
        CREATE TABLE departments (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            slug TEXT UNIQUE,
            description TEXT,
            parent_id INTEGER,
            budget REAL,
            status TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE department_agents (
            id INTEGER PRIMARY KEY,
            department_id INTEGER,
            agent_id INTEGER,
            role TEXT,
            joined_at TEXT,
            left_at TEXT,
            UNIQUE(department_id, agent_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY,
            department_id INTEGER,
            name TEXT,
            slug TEXT,
            description TEXT,
            status TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE team_x_agents (
            id INTEGER PRIMARY KEY,
            team_id INTEGER,
            agent_id INTEGER,
            role TEXT,
            joined_at TEXT,
            UNIQUE(team_id, agent_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE department_relations (
            id INTEGER PRIMARY KEY,
            dept_a_id INTEGER,
            dept_b_id INTEGER,
            relation_type TEXT,
            description TEXT,
            created_at TEXT,
            UNIQUE(dept_a_id, dept_b_id, relation_type)
        )
    ''')

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def graph_repo(kuzu_db):
    """Create GraphRepositoryDepartments with initialized schema"""
    repo = GraphRepositoryDepartments(kuzu_db)
    repo.init_schema()
    return repo


class TestSchemaInitialization:
    """Test KuzuDB schema creation"""

    def test_init_schema_succeeds(self, kuzu_db):
        """Schema initialization should succeed"""
        repo = GraphRepositoryDepartments(kuzu_db)
        repo.init_schema()  # Should not raise

    def test_schema_idempotent(self, kuzu_db):
        """Schema initialization should be idempotent"""
        repo = GraphRepositoryDepartments(kuzu_db)
        repo.init_schema()
        repo.init_schema()  # Should not raise on second call


class TestSyncFromSQLite:
    """Test SQLite to KuzuDB synchronization"""

    def test_sync_departments(self, graph_repo, sqlite_db):
        """Sync departments from SQLite"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at) VALUES (?, ?, ?, ?, ?)',
            (1, 'Engineering', 'eng', 'active', '2026-04-20T00:00:00')
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)

        result = graph_repo.kuzu.execute(
            'MATCH (d:Department {id: 1}) RETURN d.name'
        )
        assert result.has_next()
        row = result.get_next()
        assert row[0] == 'Engineering'

    def test_sync_agents(self, graph_repo, sqlite_db):
        """Sync agents from SQLite"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO agents (id, slug, name, role_type, status) VALUES (?, ?, ?, ?, ?)',
            (1, 'alice', 'Alice', 'engineer', 'active')
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)

        result = graph_repo.kuzu.execute(
            'MATCH (a:Agent {id: 1}) RETURN a.name'
        )
        assert result.has_next()
        row = result.get_next()
        assert row[0] == 'Alice'

    def test_sync_department_agents(self, graph_repo, sqlite_db):
        """Sync HAS_AGENT relationships"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at) VALUES (?, ?, ?, ?, ?)',
            (1, 'Engineering', 'eng', 'active', '2026-04-20T00:00:00')
        )
        cursor.execute(
            'INSERT INTO agents (id, slug, name, role_type, status) VALUES (?, ?, ?, ?, ?)',
            (1, 'alice', 'Alice', 'engineer', 'active')
        )
        cursor.execute(
            'INSERT INTO department_agents (id, department_id, agent_id, role, joined_at) VALUES (?, ?, ?, ?, ?)',
            (1, 1, 1, 'member', '2026-04-20T00:00:00')
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)

        result = graph_repo.kuzu.execute(
            'MATCH (d:Department {id: 1})-[rel:HAS_AGENT]->(a:Agent {id: 1}) RETURN rel.role'
        )
        assert result.has_next()
        row = result.get_next()
        assert row[0] == 'member'


class TestGetDepartmentAgents:
    """Test department agent queries"""

    def test_get_agents_in_department(self, graph_repo, sqlite_db):
        """Get all agents in a department"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at) VALUES (?, ?, ?, ?, ?)',
            (1, 'Engineering', 'eng', 'active', '2026-04-20T00:00:00')
        )
        cursor.execute(
            'INSERT INTO agents (id, slug, name, role_type, status) VALUES (?, ?, ?, ?, ?)',
            (1, 'alice', 'Alice', 'engineer', 'active')
        )
        cursor.execute(
            'INSERT INTO department_agents (id, department_id, agent_id, role, joined_at) VALUES (?, ?, ?, ?, ?)',
            (1, 1, 1, 'member', '2026-04-20T00:00:00')
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)

        agents = graph_repo.get_department_agents(1)
        assert len(agents) == 1
        assert agents[0]['agent_id'] == 1
        assert agents[0]['name'] == 'Alice'
        assert agents[0]['role'] == 'member'


class TestDepartmentHierarchy:
    """Test department hierarchy queries"""

    def test_get_child_departments(self, graph_repo, sqlite_db):
        """Get descendant departments"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at, parent_id) VALUES (?, ?, ?, ?, ?, ?)',
            (1, 'Engineering', 'eng', 'active', '2026-04-20T00:00:00', None)
        )
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at, parent_id) VALUES (?, ?, ?, ?, ?, ?)',
            (2, 'Backend', 'backend', 'active', '2026-04-20T00:00:00', 1)
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)

        descendants = graph_repo.get_department_hierarchy(1)
        assert len(descendants) == 1
        assert descendants[0]['id'] == 2
        assert descendants[0]['name'] == 'Backend'


class TestCircularDependencyDetection:
    """Test circular parent assignment detection"""

    def test_self_parent_detected(self, graph_repo, sqlite_db):
        """Assigning self as parent should be detected"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at) VALUES (?, ?, ?, ?, ?)',
            (1, 'Engineering', 'eng', 'active', '2026-04-20T00:00:00')
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)

        is_circular = graph_repo.detect_circular_parent_assignment(1, 1)
        assert is_circular is True

    def test_descendant_as_parent_detected(self, graph_repo, sqlite_db):
        """Assigning descendant as parent should be detected"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at, parent_id) VALUES (?, ?, ?, ?, ?, ?)',
            (1, 'Engineering', 'eng', 'active', '2026-04-20T00:00:00', None)
        )
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at, parent_id) VALUES (?, ?, ?, ?, ?, ?)',
            (2, 'Backend', 'backend', 'active', '2026-04-20T00:00:00', 1)
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)

        # Trying to make dept 1 parent of dept 2 when 2 is already child of 1
        is_circular = graph_repo.detect_circular_parent_assignment(2, 2)
        assert is_circular is True

    def test_valid_parent_not_detected(self, graph_repo, sqlite_db):
        """Valid parent assignment should not be detected as circular"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at) VALUES (?, ?, ?, ?, ?)',
            (1, 'Engineering', 'eng', 'active', '2026-04-20T00:00:00')
        )
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at) VALUES (?, ?, ?, ?, ?)',
            (2, 'Backend', 'backend', 'active', '2026-04-20T00:00:00')
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)

        is_circular = graph_repo.detect_circular_parent_assignment(2, 1)
        assert is_circular is False


class TestAddRemoveAgents:
    """Test dynamic agent relationship changes"""

    def test_add_agent_to_department(self, graph_repo, sqlite_db):
        """Add agent to department"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at) VALUES (?, ?, ?, ?, ?)',
            (1, 'Engineering', 'eng', 'active', '2026-04-20T00:00:00')
        )
        cursor.execute(
            'INSERT INTO agents (id, slug, name, role_type, status) VALUES (?, ?, ?, ?, ?)',
            (1, 'alice', 'Alice', 'engineer', 'active')
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)
        graph_repo.add_agent_to_department(1, 1, 'lead', '2026-04-20T00:00:00')

        result = graph_repo.kuzu.execute(
            'MATCH (d:Department {id: 1})-[rel:HAS_AGENT]->(a:Agent {id: 1}) RETURN rel.role'
        )
        assert result.has_next()
        row = result.get_next()
        assert row[0] == 'lead'

    def test_remove_agent_from_department(self, graph_repo, sqlite_db):
        """Remove agent from department"""
        cursor = sqlite_db.cursor()
        cursor.execute(
            'INSERT INTO departments (id, name, slug, status, created_at) VALUES (?, ?, ?, ?, ?)',
            (1, 'Engineering', 'eng', 'active', '2026-04-20T00:00:00')
        )
        cursor.execute(
            'INSERT INTO agents (id, slug, name, role_type, status) VALUES (?, ?, ?, ?, ?)',
            (1, 'alice', 'Alice', 'engineer', 'active')
        )
        cursor.execute(
            'INSERT INTO department_agents (id, department_id, agent_id, role, joined_at) VALUES (?, ?, ?, ?, ?)',
            (1, 1, 1, 'member', '2026-04-20T00:00:00')
        )
        sqlite_db.commit()

        graph_repo.sync_from_sqlite(sqlite_db)
        graph_repo.remove_agent_from_department(1, 1)

        result = graph_repo.kuzu.execute(
            'MATCH (d:Department {id: 1})-[rel:HAS_AGENT]->(a:Agent {id: 1}) RETURN rel'
        )
        assert not result.has_next()
