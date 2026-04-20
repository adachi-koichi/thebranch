from datetime import datetime, timedelta
from workflow.models import DevTask, TaskDependency
from workflow.repositories.base import BaseRepository


class TaskRepository(BaseRepository):
    """Data access for task layer"""

    def create_task(
        self,
        title: str,
        description: str | None,
        assignee: str,
        phase: str,
        workflow_instance_id: int,
        wf_node_key: str | None,
        status: str,
        priority: int,
        estimated_hours: float | None
    ) -> DevTask:
        """Insert dev_tasks, return with id"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO dev_tasks
            (title, description, assignee, phase, workflow_instance_id, wf_node_key,
             status, priority, estimated_hours, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        task_id = self.execute_insert(
            query,
            (
                title, description, assignee, phase, workflow_instance_id, wf_node_key,
                status, priority, estimated_hours, now
            )
        )
        return DevTask(
            id=task_id,
            title=title,
            description=description,
            assignee=assignee,
            phase=phase,
            workflow_instance_id=workflow_instance_id,
            wf_node_key=wf_node_key,
            status=status,
            priority=priority,
            estimated_hours=estimated_hours,
            created_at=datetime.fromisoformat(now)
        )

    def count_instance_tasks(self, instance_id: int) -> int:
        """Count tasks for instance (for idempotency check)"""
        query = 'SELECT COUNT(*) as count FROM dev_tasks WHERE workflow_instance_id = ?'
        row = self.execute_one(query, (instance_id,))
        return row['count'] if row else 0

    def get_instance_tasks(self, instance_id: int) -> list[DevTask]:
        """Get all tasks for instance"""
        query = 'SELECT * FROM dev_tasks WHERE workflow_instance_id = ? ORDER BY created_at ASC'
        rows = self.execute_all(query, (instance_id,))
        return [self._row_to_dev_task(row) for row in rows]

    def delete_instance_tasks(self, instance_id: int) -> None:
        """Delete all tasks for instance (on rollback)"""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM task_dependencies WHERE predecessor_id IN (SELECT id FROM dev_tasks WHERE workflow_instance_id = ?)', (instance_id,))
            cursor.execute('DELETE FROM dev_tasks WHERE workflow_instance_id = ?', (instance_id,))

    def create_task_dependency(
        self,
        predecessor_id: int,
        successor_id: int,
        dep_type: str
    ) -> TaskDependency:
        """Insert task_dependencies edge"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO task_dependencies
            (predecessor_id, successor_id, dep_type, created_at)
            VALUES (?, ?, ?, ?)
        '''
        dep_id = self.execute_insert(
            query,
            (predecessor_id, successor_id, dep_type, now)
        )
        return TaskDependency(
            id=dep_id,
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            dep_type=dep_type,
            created_at=datetime.fromisoformat(now)
        )

    def get_task(self, task_id: int) -> DevTask | None:
        """Get task"""
        query = 'SELECT * FROM dev_tasks WHERE id = ?'
        row = self.execute_one(query, (task_id,))
        if not row:
            return None
        return self._row_to_dev_task(row)

    def update_task(self, task: DevTask) -> None:
        """Update task status, completed_at, etc"""
        query = '''
            UPDATE dev_tasks
            SET status = ?, started_at = ?, completed_at = ?, unblocked_at = ?
            WHERE id = ?
        '''
        self.execute_update(
            query,
            (task.status, task.started_at, task.completed_at, task.unblocked_at, task.id)
        )

    def get_tasks_by_phase(
        self,
        instance_id: int,
        phase_key: str
    ) -> list[DevTask]:
        """Get all tasks in phase"""
        query = '''
            SELECT * FROM dev_tasks
            WHERE workflow_instance_id = ? AND phase = ?
            ORDER BY created_at ASC
        '''
        rows = self.execute_all(query, (instance_id, phase_key))
        return [self._row_to_dev_task(row) for row in rows]

    def get_task_dependencies(self, instance_id: int) -> list[TaskDependency]:
        """Get all task dependencies for instance"""
        query = '''
            SELECT td.* FROM task_dependencies td
            JOIN dev_tasks dt ON td.successor_id = dt.id
            WHERE dt.workflow_instance_id = ?
        '''
        rows = self.execute_all(query, (instance_id,))
        return [self._row_to_task_dependency(row) for row in rows]

    @staticmethod
    def _row_to_dev_task(row) -> DevTask:
        """Convert database row to DevTask"""
        version = 0
        try:
            version = row['version']
        except (IndexError, KeyError):
            version = 0
        return DevTask(
            id=row['id'],
            title=row['title'],
            description=row['description'],
            assignee=row['assignee'],
            phase=row['phase'],
            workflow_instance_id=row['workflow_instance_id'],
            wf_node_key=row['wf_node_key'],
            status=row['status'],
            priority=row['priority'],
            estimated_hours=row['estimated_hours'],
            version=version,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            unblocked_at=datetime.fromisoformat(row['unblocked_at']) if row['unblocked_at'] else None
        )

    @staticmethod
    def _row_to_task_dependency(row) -> TaskDependency:
        """Convert database row to TaskDependency"""
        return TaskDependency(
            id=row['id'],
            predecessor_id=row['predecessor_id'],
            successor_id=row['successor_id'],
            dep_type=row['dep_type'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )

    def get_or_create_task(
        self,
        title: str,
        assignee: str,
        phase: str,
        workflow_instance_id: int,
        description: str | None = None,
        wf_node_key: str | None = None,
        status: str = 'blocked',
        priority: int = 1,
        estimated_hours: float | None = None,
        dedup_window_minutes: int = 10
    ) -> DevTask:
        """Get or create task with deduplication within time window.

        Returns existing task if found with same (title, assignee, phase, instance_id)
        created within dedup_window_minutes. Otherwise creates new task.
        """
        cutoff = datetime.now() - timedelta(minutes=dedup_window_minutes)
        cutoff_str = cutoff.isoformat()

        query = '''
            SELECT * FROM dev_tasks
            WHERE title = ? AND assignee = ? AND phase = ?
                AND workflow_instance_id = ? AND created_at > ?
            ORDER BY created_at DESC
            LIMIT 1
        '''
        row = self.execute_one(query, (title, assignee, phase, workflow_instance_id, cutoff_str))
        if row:
            return self._row_to_dev_task(row)

        return self.create_task(
            title=title,
            description=description,
            assignee=assignee,
            phase=phase,
            workflow_instance_id=workflow_instance_id,
            wf_node_key=wf_node_key,
            status=status,
            priority=priority,
            estimated_hours=estimated_hours
        )

    def update_task_with_version(
        self,
        task_id: int,
        current_version: int,
        new_status: str,
        new_version: int | None = None
    ) -> bool:
        """Update task using optimistic locking (CAS pattern).

        Returns True if update succeeded, False if version conflict detected.
        Increments version on successful update.
        """
        if new_version is None:
            new_version = current_version + 1

        query = '''
            UPDATE dev_tasks
            SET status = ?, version = ?, updated_at = ?
            WHERE id = ? AND version = ?
        '''
        now = datetime.now().isoformat()

        cursor = self.db.cursor()
        cursor.execute(query, (new_status, new_version, now, task_id, current_version))
        self.db.commit()

        return cursor.rowcount > 0
