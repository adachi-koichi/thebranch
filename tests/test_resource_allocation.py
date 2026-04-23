"""
Test suite for Resource Allocation functionality
Tests ResourceAllocator class, API endpoints, and edge cases
"""

import pytest
import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.resource_allocator import ResourceAllocator


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary SQLite database for testing"""
    db_file = tmp_path / "test.db"
    return db_file


@pytest.fixture
def test_db(test_db_path):
    """Initialize test database with schema"""
    conn = sqlite3.connect(str(test_db_path))
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            status TEXT DEFAULT 'active'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS department_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL,
            resource_type TEXT NOT NULL,
            total_allocated INTEGER NOT NULL,
            current_used INTEGER DEFAULT 0,
            reserved INTEGER DEFAULT 0,
            unit TEXT DEFAULT 'units',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(department_id, resource_type)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resource_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL,
            resource_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            priority INTEGER DEFAULT 3,
            status TEXT DEFAULT 'pending',
            allocated_at TIMESTAMP,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resource_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL,
            resource_type TEXT NOT NULL,
            required_amount INTEGER NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            approved_amount INTEGER,
            approval_reason TEXT,
            approved_by TEXT,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test departments
    cursor.execute("INSERT INTO departments (id, name, slug) VALUES (1, 'Dept A', 'dept-a')")
    cursor.execute("INSERT INTO departments (id, name, slug) VALUES (2, 'Dept B', 'dept-b')")

    conn.commit()
    conn.close()

    yield test_db_path


@pytest.fixture
def allocator(test_db):
    """Create ResourceAllocator instance for testing"""
    return ResourceAllocator(test_db)


class TestResourceAllocatorAvailability:
    """Tests for check_availability method"""

    def test_check_availability_no_resources(self, allocator):
        """Test availability check when no resources exist"""
        result = allocator.check_availability("cpu", 10)
        assert result is False

    def test_check_availability_sufficient(self, allocator, test_db):
        """Test availability check with sufficient resources"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'cpu', 100, 30, 20)"""
        )
        conn.commit()
        conn.close()

        result = allocator.check_availability("cpu", 40)
        assert result is True

    def test_check_availability_insufficient(self, allocator, test_db):
        """Test availability check with insufficient resources"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'cpu', 100, 70, 20)"""
        )
        conn.commit()
        conn.close()

        result = allocator.check_availability("cpu", 15)
        assert result is False

    def test_check_availability_multiple_departments(self, allocator, test_db):
        """Test availability with resources from multiple departments"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'memory', 1000, 300, 200)"""
        )
        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (2, 'memory', 500, 100, 100)"""
        )
        conn.commit()
        conn.close()

        # Total: 1500, Used: 400, Reserved: 300 -> Available: 800
        result = allocator.check_availability("memory", 700)
        assert result is True

        result = allocator.check_availability("memory", 900)
        assert result is False


class TestResourceAllocatorAllocation:
    """Tests for allocate_resource method"""

    def test_allocate_to_existing_resource(self, allocator, test_db):
        """Test allocating to existing resource"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'api_calls', 1000, 200, 100)"""
        )
        conn.commit()
        conn.close()

        result = allocator.allocate_resource(1, "api_calls", 500)
        assert result is True

        # Verify allocation
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resource_allocations WHERE department_id = 1")
        allocation = cursor.fetchone()
        assert allocation is not None
        assert allocation["amount"] == 500
        assert allocation["status"] == "active"

        # Verify reserved amount updated
        cursor.execute(
            "SELECT reserved FROM department_resources WHERE department_id = 1 AND resource_type = 'api_calls'"
        )
        resource = cursor.fetchone()
        assert resource["reserved"] == 600  # 100 + 500
        conn.close()

    def test_allocate_to_new_resource(self, allocator):
        """Test allocating to non-existent resource creates new entry"""
        result = allocator.allocate_resource(1, "threads", 50)
        assert result is True

    def test_allocate_insufficient_resources(self, allocator, test_db):
        """Test allocation fails with insufficient resources"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'cpu', 100, 60, 30)"""
        )
        conn.commit()
        conn.close()

        result = allocator.allocate_resource(1, "cpu", 20)
        assert result is False


class TestResourceAllocatorDeallocation:
    """Tests for deallocate_resource method"""

    def test_deallocate_existing_allocation(self, allocator, test_db):
        """Test deallocating existing allocation"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Create resource and allocation
        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'memory', 500, 100, 200)"""
        )
        cursor.execute(
            """INSERT INTO resource_allocations
               (department_id, resource_type, amount, status)
               VALUES (1, 'memory', 200, 'active')"""
        )
        conn.commit()
        allocation_id = cursor.lastrowid
        conn.close()

        result = allocator.deallocate_resource(allocation_id)
        assert result is True

        # Verify status changed
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM resource_allocations WHERE id = ?", (allocation_id,))
        allocation = cursor.fetchone()
        assert allocation["status"] == "completed"

        # Verify reserved reduced
        cursor.execute("SELECT reserved FROM department_resources WHERE department_id = 1")
        resource = cursor.fetchone()
        assert resource["reserved"] == 0  # 200 - 200
        conn.close()

    def test_deallocate_nonexistent_allocation(self, allocator):
        """Test deallocating non-existent allocation"""
        result = allocator.deallocate_resource(9999)
        assert result is False


class TestResourceAllocatorSummary:
    """Tests for get_department_resource_summary method"""

    def test_get_summary_empty(self, allocator):
        """Test summary for department with no resources"""
        summary = allocator.get_department_resource_summary(1)
        assert summary["department_id"] == 1
        assert len(summary["resources"]) == 0
        assert summary["total_resources"] == 0

    def test_get_summary_with_resources(self, allocator, test_db):
        """Test summary with multiple resources"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'cpu', 100, 30, 20)"""
        )
        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'memory', 1000, 300, 200)"""
        )
        conn.commit()
        conn.close()

        summary = allocator.get_department_resource_summary(1)
        assert summary["department_id"] == 1
        assert summary["total_resources"] == 2
        assert summary["utilization_percent"] > 0

    def test_get_summary_with_allocations(self, allocator, test_db):
        """Test summary includes active allocations"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'api_calls', 5000, 1000, 500)"""
        )
        cursor.execute(
            """INSERT INTO resource_allocations
               (department_id, resource_type, amount, status)
               VALUES (1, 'api_calls', 500, 'active')"""
        )
        cursor.execute(
            """INSERT INTO resource_allocations
               (department_id, resource_type, amount, status)
               VALUES (1, 'api_calls', 300, 'active')"""
        )
        conn.commit()
        conn.close()

        summary = allocator.get_department_resource_summary(1)
        assert len(summary["allocations"]) == 1  # Grouped by resource_type
        assert summary["allocations"][0]["total_allocated"] == 800


class TestResourceAllocatorRequests:
    """Tests for get_resource_requests method"""

    def test_get_requests_empty(self, allocator):
        """Test getting requests when none exist"""
        requests = allocator.get_resource_requests()
        assert len(requests) == 0

    def test_get_requests_all(self, allocator, test_db):
        """Test getting all requests"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO resource_requests
               (department_id, resource_type, required_amount, status)
               VALUES (1, 'cpu', 100, 'pending')"""
        )
        cursor.execute(
            """INSERT INTO resource_requests
               (department_id, resource_type, required_amount, status)
               VALUES (2, 'memory', 500, 'approved')"""
        )
        conn.commit()
        conn.close()

        requests = allocator.get_resource_requests()
        assert len(requests) == 2

    def test_get_requests_by_department(self, allocator, test_db):
        """Test getting requests filtered by department"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO resource_requests
               (department_id, resource_type, required_amount, status)
               VALUES (1, 'cpu', 100, 'pending')"""
        )
        cursor.execute(
            """INSERT INTO resource_requests
               (department_id, resource_type, required_amount, status)
               VALUES (2, 'memory', 500, 'approved')"""
        )
        conn.commit()
        conn.close()

        requests = allocator.get_resource_requests(department_id=1)
        assert len(requests) == 1
        assert requests[0]["department_id"] == 1


class TestResourceAllocatorUsageUpdate:
    """Tests for update_resource_usage method"""

    def test_update_usage(self, allocator, test_db):
        """Test updating resource usage"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO department_resources
               (department_id, resource_type, total_allocated, current_used, reserved)
               VALUES (1, 'cpu', 100, 30, 20)"""
        )
        conn.commit()
        conn.close()

        result = allocator.update_resource_usage(1, "cpu", 50)
        assert result is True

        # Verify update
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT current_used FROM department_resources WHERE department_id = 1 AND resource_type = 'cpu'"
        )
        resource = cursor.fetchone()
        assert resource["current_used"] == 50
        conn.close()

    def test_update_usage_nonexistent(self, allocator):
        """Test updating usage for non-existent resource"""
        result = allocator.update_resource_usage(1, "nonexistent", 100)
        # Should still return True (SQL doesn't error), but no rows updated
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
