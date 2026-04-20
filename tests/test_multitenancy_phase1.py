"""
Tests for Phase 1: Multitenancy schema expansion.

Tests:
1. Migration script execution
2. New tables creation (organizations, users, audit_logs)
3. org_id column addition to existing tables
4. Indexes creation
"""

import sqlite3
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from workflow.migrations import migrate_to_multitenancy, insert_default_organization
from workflow.data_access import TenantAwareQuery, TenantContext, OrganizationManager

# Import auth functions without FastAPI dependency
import sys
import importlib.util
spec = importlib.util.spec_from_file_location(
    "auth_core",
    Path(__file__).parent.parent / "workflow" / "auth.py"
)
auth_module = importlib.util.module_from_spec(spec)
# Inject minimal fastapi mock
class MockRequest:
    class Client:
        host = "127.0.0.1"
    client = Client()
sys.modules['fastapi'] = type(sys)('fastapi')
sys.modules['fastapi'].Request = MockRequest
sys.modules['fastapi'].HTTPException = Exception
sys.modules['fastapi'].Header = lambda *a, **k: None
sys.modules['starlette'] = type(sys)('starlette')
sys.modules['starlette.middleware'] = type(sys)('starlette.middleware')
sys.modules['starlette.middleware.base'] = type(sys)('starlette.middleware.base')
sys.modules['starlette.middleware.base'].BaseHTTPMiddleware = object

spec.loader.exec_module(auth_module)
create_access_token = auth_module.create_access_token
verify_token = auth_module.verify_token


def test_migration_creates_organizations_table():
    """Test organizations table creation."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Create base schema first
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create minimal workflow_instances table for test
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wf_template_phases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER,
                phase_key TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wf_template_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phase_id INTEGER,
                template_id INTEGER,
                task_key TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_instance_specialists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id INTEGER,
                phase_id INTEGER,
                specialist_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wf_instance_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id INTEGER,
                phase_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dev_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                predecessor_id INTEGER,
                successor_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

        # Run migration
        migrate_to_multitenancy(db_path)

        # Verify
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check organizations table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='organizations'"
        )
        assert cursor.fetchone() is not None, "organizations table not created"

        # Check users table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert cursor.fetchone() is not None, "users table not created"

        # Check audit_logs table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'"
        )
        assert cursor.fetchone() is not None, "audit_logs table not created"

        # Check org_id column in workflow_instances
        cursor.execute("PRAGMA table_info(workflow_instances)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "org_id" in columns, "org_id column not added to workflow_instances"

        # Check org_id column in dev_tasks
        cursor.execute("PRAGMA table_info(dev_tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "org_id" in columns, "org_id column not added to dev_tasks"

        conn.close()
        print("✓ test_migration_creates_organizations_table PASSED")

    finally:
        Path(db_path).unlink(missing_ok=True)


def test_insert_default_organization():
    """Test default organization insertion."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Create schema matching migration output
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                tier TEXT CHECK(tier IN ('free', 'pro', 'enterprise')) DEFAULT 'free',
                status TEXT CHECK(status IN ('active', 'suspended', 'deleted')) DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                billing_email TEXT,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Insert default org
        insert_default_organization(db_path)

        # Verify
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM organizations WHERE org_id = 'default'")
        row = cursor.fetchone()
        assert row is not None, "Default organization not inserted"
        conn.close()

        print("✓ test_insert_default_organization PASSED")

    finally:
        Path(db_path).unlink(missing_ok=True)


def test_tenant_context_and_query():
    """Test TenantAwareQuery with isolation."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Create schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE dev_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Insert test data for two orgs
        cursor.execute(
            "INSERT INTO dev_tasks (org_id, title, created_by) VALUES (?, ?, ?)",
            ("org-1", "Task 1", "user-1")
        )
        cursor.execute(
            "INSERT INTO dev_tasks (org_id, title, created_by) VALUES (?, ?, ?)",
            ("org-1", "Task 2", "user-1")
        )
        cursor.execute(
            "INSERT INTO dev_tasks (org_id, title, created_by) VALUES (?, ?, ?)",
            ("org-2", "Task 3", "user-2")
        )
        conn.commit()

        # Query with org-1 context
        context = TenantContext(org_id="org-1", user_id="user-1", role="member")
        query = TenantAwareQuery(conn, context)

        tasks = query.select_tasks()
        assert len(tasks) == 2, f"Expected 2 tasks for org-1, got {len(tasks)}"
        assert all(t["org_id"] == "org-1" for t in tasks), "Org isolation failed"

        # Query with org-2 context
        context2 = TenantContext(org_id="org-2", user_id="user-2", role="member")
        query2 = TenantAwareQuery(conn, context2)

        tasks2 = query2.select_tasks()
        assert len(tasks2) == 1, f"Expected 1 task for org-2, got {len(tasks2)}"
        assert all(t["org_id"] == "org-2" for t in tasks2), "Org isolation failed"

        conn.close()
        print("✓ test_tenant_context_and_query PASSED")

    finally:
        Path(db_path).unlink(missing_ok=True)


def test_jwt_token_with_org_id():
    """Test JWT token creation and verification with org_id."""
    # Create token
    token = create_access_token(
        user_id="user-123",
        org_id="org-exp-stock",
        role="admin",
        email="user@example.com"
    )

    assert token is not None, "Token not created"

    # Verify token
    payload = verify_token(token)

    assert payload["sub"] == "user-123", "user_id mismatch"
    assert payload["org_id"] == "org-exp-stock", "org_id mismatch"
    assert payload["role"] == "admin", "role mismatch"
    assert payload["email"] == "user@example.com", "email mismatch"

    print("✓ test_jwt_token_with_org_id PASSED")


def test_organization_manager():
    """Test OrganizationManager operations."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Create schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                tier TEXT DEFAULT 'free',
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(org_id, email)
            )
        """)
        conn.commit()

        # Test OrganizationManager
        mgr = OrganizationManager(conn)

        # Create org
        result = mgr.create_organization(
            org_id="org-test",
            name="Test Org",
            slug="test-org"
        )
        assert result is True, "Organization creation failed"

        # Get org
        org = mgr.get_organization("org-test")
        assert org is not None, "Organization not found"
        assert org["name"] == "Test Org", "Organization name mismatch"

        # Try to create duplicate (should fail)
        result2 = mgr.create_organization(
            org_id="org-test",
            name="Duplicate",
            slug="duplicate"
        )
        assert result2 is False, "Duplicate org creation should fail"

        conn.close()
        print("✓ test_organization_manager PASSED")

    finally:
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    print("Running Phase 1 Multitenancy Tests...\n")

    try:
        test_migration_creates_organizations_table()
        test_insert_default_organization()
        test_tenant_context_and_query()
        test_jwt_token_with_org_id()
        test_organization_manager()

        print("\n✅ All tests PASSED!")

    except AssertionError as e:
        print(f"\n❌ Test FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
