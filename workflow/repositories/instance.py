import json
from datetime import datetime
from typing import Any
from workflow.models import WorkflowInstance, PhaseInstance, DevTask, Agent
from workflow.repositories.base import BaseRepository


class InstanceRepository(BaseRepository):
    """Data access for instance layer"""

    def create_instance(
        self,
        template_id: int,
        name: str,
        status: str,
        context: dict[str, Any]
    ) -> WorkflowInstance:
        """Insert workflow_instances, return with id"""
        now = datetime.now().isoformat()
        context_json = json.dumps(context) if context else None
        query = '''
            INSERT INTO workflow_instances
            (template_id, name, status, context, created_at)
            VALUES (?, ?, ?, ?, ?)
        '''
        instance_id = self.execute_insert(
            query,
            (template_id, name, status, context_json, now)
        )
        return WorkflowInstance(
            id=instance_id,
            template_id=template_id,
            name=name,
            status=status,
            context=context,
            created_at=datetime.fromisoformat(now)
        )

    def get_instance(self, instance_id: int) -> WorkflowInstance | None:
        """Get instance"""
        query = 'SELECT * FROM workflow_instances WHERE id = ?'
        row = self.execute_one(query, (instance_id,))
        if not row:
            return None
        return self._row_to_instance(row)

    def update_instance(self, instance: WorkflowInstance) -> None:
        """Update instance (mainly status)"""
        now = datetime.now().isoformat()
        query = '''
            UPDATE workflow_instances
            SET status = ?, started_at = ?, completed_at = ?
            WHERE id = ?
        '''
        self.execute_update(
            query,
            (instance.status, instance.started_at, instance.completed_at, instance.id)
        )

    def delete_instance(self, instance_id: int) -> None:
        """Delete instance and all related data (cascade)"""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM task_dependencies WHERE predecessor_id IN (SELECT id FROM dev_tasks WHERE workflow_instance_id = ?)', (instance_id,))
            cursor.execute('DELETE FROM dev_tasks WHERE workflow_instance_id = ?', (instance_id,))
            cursor.execute('DELETE FROM wf_instance_nodes WHERE instance_id = ?', (instance_id,))
            cursor.execute('DELETE FROM workflow_instance_specialists WHERE instance_id = ?', (instance_id,))
            cursor.execute('DELETE FROM workflow_instances WHERE id = ?', (instance_id,))

    def assign_specialist(
        self,
        instance_id: int,
        phase_id: int,
        specialist_id: int,
        specialist_slug: str,
        specialist_name: str
    ) -> None:
        """Insert workflow_instance_specialists"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO workflow_instance_specialists
            (instance_id, phase_id, specialist_id, specialist_slug, specialist_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        self.execute_insert(
            query,
            (instance_id, phase_id, specialist_id, specialist_slug, specialist_name, now)
        )

    def create_phase_instance(
        self,
        instance_id: int,
        phase_id: int,
        phase_key: str,
        status: str
    ) -> PhaseInstance:
        """Insert wf_instance_nodes for phase, return with id"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO wf_instance_nodes
            (instance_id, phase_id, phase_key, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        '''
        phase_instance_id = self.execute_insert(
            query,
            (instance_id, phase_id, phase_key, status, now)
        )
        return PhaseInstance(
            id=phase_instance_id,
            instance_id=instance_id,
            phase_id=phase_id,
            phase_key=phase_key,
            status=status,
            created_at=datetime.fromisoformat(now)
        )

    def get_phase_instance(
        self,
        instance_id: int,
        phase_key: str
    ) -> PhaseInstance | None:
        """Get phase instance by phase_key"""
        query = '''
            SELECT * FROM wf_instance_nodes
            WHERE instance_id = ? AND phase_key = ?
        '''
        row = self.execute_one(query, (instance_id, phase_key))
        if not row:
            return None
        return self._row_to_phase_instance(row)

    def get_phase_instances(self, instance_id: int) -> list[PhaseInstance]:
        """Get all phases for instance, sorted by phase_order"""
        query = '''
            SELECT n.* FROM wf_instance_nodes n
            JOIN wf_template_phases p ON n.phase_id = p.id
            WHERE n.instance_id = ?
            ORDER BY p.phase_order ASC
        '''
        rows = self.execute_all(query, (instance_id,))
        return [self._row_to_phase_instance(row) for row in rows]

    def update_phase_instance(self, phase: PhaseInstance) -> None:
        """Update phase instance"""
        query = '''
            UPDATE wf_instance_nodes
            SET status = ?, started_at = ?, completed_at = ?
            WHERE id = ?
        '''
        self.execute_update(
            query,
            (phase.status, phase.started_at, phase.completed_at, phase.id)
        )

    def get_instance_tasks(self, instance_id: int) -> list[DevTask]:
        """Get all tasks for instance"""
        query = '''
            SELECT * FROM dev_tasks
            WHERE workflow_instance_id = ?
            ORDER BY created_at ASC
        '''
        rows = self.execute_all(query, (instance_id,))
        return [self._row_to_dev_task(row) for row in rows]

    def get_phase_specialist(self, instance_id: int, phase_id: int) -> Agent | None:
        """Get specialist assigned to phase within instance"""
        query = '''
            SELECT a.* FROM agents a
            JOIN workflow_instance_specialists s
            ON a.id = s.specialist_id
            WHERE s.instance_id = ? AND s.phase_id = ?
        '''
        row = self.execute_one(query, (instance_id, phase_id))
        if not row:
            return None
        return self._row_to_agent(row)

    def list_instances(
        self,
        template_id: int | None,
        status: str | None,
        limit: int,
        offset: int
    ) -> list[WorkflowInstance]:
        """List instances with pagination"""
        conditions = []
        params = []

        if template_id is not None:
            conditions.append('template_id = ?')
            params.append(template_id)

        if status:
            conditions.append('status = ?')
            params.append(status)

        where_clause = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
        query = f'''
            SELECT * FROM workflow_instances
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        '''
        params.extend([limit, offset])
        rows = self.execute_all(query, tuple(params))
        return [self._row_to_instance(row) for row in rows]

    @staticmethod
    def _row_to_instance(row) -> WorkflowInstance:
        """Convert database row to WorkflowInstance"""
        context = json.loads(row['context']) if row['context'] else None
        return WorkflowInstance(
            id=row['id'],
            template_id=row['template_id'],
            name=row['name'],
            status=row['status'],
            context=context,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None
        )

    @staticmethod
    def _row_to_phase_instance(row) -> PhaseInstance:
        """Convert database row to PhaseInstance"""
        return PhaseInstance(
            id=row['id'],
            instance_id=row['instance_id'],
            phase_id=row['phase_id'],
            phase_key=row['phase_key'],
            status=row['status'],
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )

    @staticmethod
    def _row_to_dev_task(row) -> DevTask:
        """Convert database row to DevTask"""
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
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            unblocked_at=datetime.fromisoformat(row['unblocked_at']) if row['unblocked_at'] else None
        )

    @staticmethod
    def _row_to_agent(row) -> Agent:
        """Convert database row to Agent"""
        return Agent(
            id=row['id'],
            name=row['name'],
            email=row['email'],
            specialist_type=row['specialist_type'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )
