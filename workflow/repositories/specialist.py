from datetime import datetime
from workflow.models import Agent, Phase
from workflow.repositories.base import BaseRepository


class SpecialistRepository(BaseRepository):
    """Data access for specialist/agent layer"""

    def create_agent(
        self,
        name: str,
        email: str,
        specialist_type: str
    ) -> Agent:
        """Insert agents, return with id"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO agents (name, email, specialist_type, created_at)
            VALUES (?, ?, ?, ?)
        '''
        agent_id = self.execute_insert(
            query,
            (name, email, specialist_type, now)
        )
        return Agent(
            id=agent_id,
            name=name,
            email=email,
            specialist_type=specialist_type,
            created_at=datetime.fromisoformat(now)
        )

    def get_agent(self, agent_id: int) -> Agent | None:
        """Get agent by id"""
        query = 'SELECT * FROM agents WHERE id = ?'
        row = self.execute_one(query, (agent_id,))
        if not row:
            return None
        return self._row_to_agent(row)

    def get_agent_by_email(self, email: str) -> Agent | None:
        """Get agent by email"""
        query = 'SELECT * FROM agents WHERE email = ?'
        row = self.execute_one(query, (email,))
        if not row:
            return None
        return self._row_to_agent(row)

    def get_agent_by_name(self, name: str) -> Agent | None:
        """Get agent by name (case-insensitive)"""
        query = 'SELECT * FROM agents WHERE LOWER(name) = LOWER(?)'
        row = self.execute_one(query, (name,))
        if not row:
            return None
        return self._row_to_agent(row)

    def get_agents(
        self,
        specialist_type: str | None = None
    ) -> list[Agent]:
        """Get all agents, optional type filter"""
        if specialist_type:
            query = '''
                SELECT * FROM agents
                WHERE specialist_type = ?
                ORDER BY name ASC
            '''
            rows = self.execute_all(query, (specialist_type,))
        else:
            query = 'SELECT * FROM agents ORDER BY name ASC'
            rows = self.execute_all(query)
        return [self._row_to_agent(row) for row in rows]

    def get_template_phases(self, template_id: int) -> list[Phase]:
        """Get all phases for template (for assignment validation)"""
        query = '''
            SELECT * FROM wf_template_phases
            WHERE template_id = ?
            ORDER BY phase_order ASC
        '''
        rows = self.execute_all(query, (template_id,))
        return [self._row_to_phase(row) for row in rows]

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
