from datetime import datetime
from workflow.models import Template, Phase, TaskDef
from workflow.repositories.base import BaseRepository


class TemplateRepository(BaseRepository):
    """Data access for template layer"""

    def create_template(
        self,
        name: str,
        description: str | None,
        created_by: str | None,
        status: str
    ) -> Template:
        """Insert new template, return with id assigned"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO workflow_templates (name, description, status, created_at, updated_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        template_id = self.execute_insert(
            query,
            (name, description, status, now, now, created_by)
        )
        return Template(
            id=template_id,
            name=name,
            description=description,
            status=status,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            created_by=created_by
        )

    def get_template(self, template_id: int) -> Template | None:
        """Get template (shallow, without phases)"""
        query = 'SELECT * FROM workflow_templates WHERE id = ?'
        row = self.execute_one(query, (template_id,))
        if not row:
            return None
        return self._row_to_template(row)

    def get_template_with_phases_and_tasks(
        self,
        template_id: int
    ) -> Template | None:
        """Get template with nested phases and tasks"""
        template = self.get_template(template_id)
        if not template:
            return None

        phases = self.get_phases(template_id)
        for phase in phases:
            phase.tasks = self.get_tasks_for_phase(phase.id)

        template.phases = phases
        return template

    def update_template(self, template: Template) -> None:
        """Update template (mainly status)"""
        now = datetime.now().isoformat()
        query = '''
            UPDATE workflow_templates
            SET status = ?, updated_at = ?
            WHERE id = ?
        '''
        self.execute_update(query, (template.status, now, template.id))

    def create_phase(
        self,
        template_id: int,
        phase_key: str,
        phase_label: str,
        specialist_type: str,
        phase_order: int,
        is_parallel: bool
    ) -> Phase:
        """Insert phase, return with id assigned"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO wf_template_phases
            (template_id, phase_key, phase_label, specialist_type, phase_order, is_parallel, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        phase_id = self.execute_insert(
            query,
            (template_id, phase_key, phase_label, specialist_type, phase_order, is_parallel, now)
        )
        return Phase(
            id=phase_id,
            template_id=template_id,
            phase_key=phase_key,
            phase_label=phase_label,
            specialist_type=specialist_type,
            phase_order=phase_order,
            is_parallel=is_parallel,
            created_at=datetime.fromisoformat(now)
        )

    def get_phase(self, phase_id: int) -> Phase | None:
        """Get phase by id"""
        query = 'SELECT * FROM wf_template_phases WHERE id = ?'
        row = self.execute_one(query, (phase_id,))
        if not row:
            return None
        return self._row_to_phase(row)

    def get_phases(self, template_id: int) -> list[Phase]:
        """Get all phases for template, sorted by phase_order"""
        query = '''
            SELECT * FROM wf_template_phases
            WHERE template_id = ?
            ORDER BY phase_order ASC
        '''
        rows = self.execute_all(query, (template_id,))
        return [self._row_to_phase(row) for row in rows]

    def create_task_def(
        self,
        phase_id: int,
        template_id: int,
        task_key: str,
        task_title: str,
        task_description: str | None,
        depends_on_key: str | None,
        priority: int,
        estimated_hours: float | None,
        task_order: int
    ) -> TaskDef:
        """Insert task definition, return with id assigned"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO wf_template_tasks
            (phase_id, template_id, task_key, task_title, task_description, depends_on_key,
             priority, estimated_hours, task_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        task_id = self.execute_insert(
            query,
            (
                phase_id, template_id, task_key, task_title, task_description,
                depends_on_key, priority, estimated_hours, task_order, now
            )
        )
        return TaskDef(
            id=task_id,
            phase_id=phase_id,
            template_id=template_id,
            task_key=task_key,
            task_title=task_title,
            task_description=task_description,
            depends_on_key=depends_on_key,
            priority=priority,
            estimated_hours=estimated_hours,
            task_order=task_order,
            created_at=datetime.fromisoformat(now)
        )

    def get_task_def(self, task_def_id: int) -> TaskDef | None:
        """Get task definition by id"""
        query = 'SELECT * FROM wf_template_tasks WHERE id = ?'
        row = self.execute_one(query, (task_def_id,))
        if not row:
            return None
        return self._row_to_task_def(row)

    def get_tasks_for_phase(self, phase_id: int) -> list[TaskDef]:
        """Get all tasks for phase, sorted by task_order"""
        query = '''
            SELECT * FROM wf_template_tasks
            WHERE phase_id = ?
            ORDER BY task_order ASC
        '''
        rows = self.execute_all(query, (phase_id,))
        return [self._row_to_task_def(row) for row in rows]

    def list_templates(
        self,
        status: str | None,
        limit: int,
        offset: int
    ) -> list[Template]:
        """List templates with pagination"""
        if status:
            query = '''
                SELECT * FROM workflow_templates
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            '''
            rows = self.execute_all(query, (status, limit, offset))
        else:
            query = '''
                SELECT * FROM workflow_templates
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            '''
            rows = self.execute_all(query, (limit, offset))
        return [self._row_to_template(row) for row in rows]

    @staticmethod
    def _row_to_template(row) -> Template:
        """Convert database row to Template"""
        return Template(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            status=row['status'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            created_by=row['created_by']
        )

    @staticmethod
    def _row_to_phase(row) -> Phase:
        """Convert database row to Phase"""
        return Phase(
            id=row['id'],
            template_id=row['template_id'],
            phase_key=row['phase_key'],
            phase_label=row['phase_label'],
            specialist_type=row['specialist_type'],
            phase_order=row['phase_order'],
            is_parallel=bool(row['is_parallel']),
            task_count=row['task_count'] or 0,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )

    @staticmethod
    def _row_to_task_def(row) -> TaskDef:
        """Convert database row to TaskDef"""
        return TaskDef(
            id=row['id'],
            phase_id=row['phase_id'],
            template_id=row['template_id'],
            task_key=row['task_key'],
            task_title=row['task_title'],
            task_description=row['task_description'],
            category=row['category'] if 'category' in row.keys() else None,
            depends_on_key=row['depends_on_key'],
            priority=row['priority'],
            estimated_hours=row['estimated_hours'],
            task_order=row['task_order'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )
