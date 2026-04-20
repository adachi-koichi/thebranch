"""
Data access layer with tenant isolation.

Implements:
1. Row-level filtering with org_id
2. Query builders with tenant context
3. Safe CRUD operations
"""

import sqlite3
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class TenantContext:
    """Context for tenant-scoped database operations."""
    org_id: str
    user_id: str
    role: str


class TenantAwareQuery:
    """
    Query builder for tenant-isolated database operations.

    Ensures all queries include org_id filter.
    """

    def __init__(self, db_connection: sqlite3.Connection, context: TenantContext):
        """
        Initialize with database connection and tenant context.

        Args:
            db_connection: SQLite connection
            context: TenantContext (org_id, user_id, role)
        """
        self.conn = db_connection
        self.context = context
        self.conn.row_factory = sqlite3.Row

    def select_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Select tasks for current organization with optional filtering.

        Args:
            status: Filter by status
            limit: Result limit

        Returns:
            List of tasks (org_id filtered)
        """
        query = "SELECT * FROM dev_tasks WHERE org_id = ?"
        params = [self.context.org_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += f" ORDER BY id DESC LIMIT {limit}"

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Get single task with tenant isolation.

        Args:
            task_id: Task ID

        Returns:
            Task dict or None if not found or not in org
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM dev_tasks WHERE id = ? AND org_id = ?",
            (task_id, self.context.org_id)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_task(
        self,
        title: str,
        description: str = None,
        status: str = "pending",
        priority: int = 1
    ) -> int:
        """
        Create task in current organization.

        org_id is forced and cannot be overridden.

        Args:
            title: Task title
            description: Task description
            status: Task status
            priority: Task priority (1-5)

        Returns:
            New task ID

        Raises:
            sqlite3.Error: If creation fails
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO dev_tasks
            (org_id, title, description, status, priority, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (self.context.org_id, title, description, status, priority, self.context.user_id)
        )

        self.conn.commit()
        return cursor.lastrowid

    def update_task(
        self,
        task_id: int,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update task with tenant isolation.

        Ensures task belongs to current org before updating.

        Args:
            task_id: Task ID
            updates: Dict of fields to update {field: value}

        Returns:
            True if updated, False if not found or not in org

        Raises:
            ValueError: If org_id in updates (forbidden)
        """
        # Prevent org_id override
        if "org_id" in updates:
            raise ValueError("Cannot change org_id")

        # Check task exists in org
        if not self.get_task(task_id):
            return False

        # Build update query
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [task_id, self.context.org_id]

        query = f"UPDATE dev_tasks SET {set_clause} WHERE id = ? AND org_id = ?"

        cursor = self.conn.cursor()
        cursor.execute(query, values)
        self.conn.commit()

        return cursor.rowcount > 0

    def delete_task(self, task_id: int) -> bool:
        """
        Soft delete task (mark as deleted).

        Ensures task belongs to current org.

        Args:
            task_id: Task ID

        Returns:
            True if deleted, False if not found or not in org
        """
        if not self.get_task(task_id):
            return False

        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE dev_tasks SET status = 'deleted' WHERE id = ? AND org_id = ?",
            (task_id, self.context.org_id)
        )
        self.conn.commit()

        return cursor.rowcount > 0

    def select_workflows(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Select workflow instances for current organization.

        Args:
            status: Filter by status
            limit: Result limit

        Returns:
            List of workflow instances (org_id filtered)
        """
        query = "SELECT * FROM workflow_instances WHERE org_id = ?"
        params = [self.context.org_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += f" ORDER BY id DESC LIMIT {limit}"

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_workflow(self, workflow_id: int) -> Optional[Dict[str, Any]]:
        """
        Get single workflow instance with tenant isolation.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            Workflow dict or None if not found or not in org
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM workflow_instances WHERE id = ? AND org_id = ?",
            (workflow_id, self.context.org_id)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_workflow(
        self,
        template_id: int,
        name: str,
        project: str = None,
        context: str = None
    ) -> int:
        """
        Create workflow instance in current organization.

        Args:
            template_id: Workflow template ID
            name: Workflow name
            project: Project name
            context: Context data (JSON)

        Returns:
            New workflow instance ID
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO workflow_instances
            (org_id, template_id, name, project, context, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (self.context.org_id, template_id, name, project, context)
        )

        self.conn.commit()
        return cursor.lastrowid


class OrganizationManager:
    """Management operations for organizations."""

    def __init__(self, db_connection: sqlite3.Connection):
        """Initialize with database connection."""
        self.conn = db_connection
        self.conn.row_factory = sqlite3.Row

    def create_organization(
        self,
        org_id: str,
        name: str,
        slug: str,
        tier: str = "free"
    ) -> bool:
        """
        Create new organization.

        Args:
            org_id: Organization ID
            name: Organization name
            slug: URL-friendly slug
            tier: Billing tier (free, pro, enterprise)

        Returns:
            True if created, False if already exists
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO organizations (org_id, name, slug, tier, status)
                VALUES (?, ?, ?, ?, 'active')
                """,
                (org_id, name, slug, tier)
            )
            self.conn.commit()
            return True

        except sqlite3.IntegrityError:
            return False

    def get_organization(self, org_id: str) -> Optional[Dict[str, Any]]:
        """
        Get organization by org_id.

        Args:
            org_id: Organization ID

        Returns:
            Organization dict or None
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM organizations WHERE org_id = ?", (org_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_users_in_org(self, org_id: str) -> List[Dict[str, Any]]:
        """
        List all users in organization.

        Args:
            org_id: Organization ID

        Returns:
            List of users
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, user_id, email, role, status FROM users WHERE org_id = ? ORDER BY created_at",
            (org_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
