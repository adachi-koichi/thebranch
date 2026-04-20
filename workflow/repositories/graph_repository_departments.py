"""KuzuDB GraphRepository for department management"""
from workflow.repositories.kuzu_connection import KuzuConnection
import sqlite3


class GraphRepositoryDepartments:
    """KuzuDB graph operations for department hierarchy and relationships"""

    def __init__(self, kuzu_conn: KuzuConnection):
        """Initialize with KuzuDB connection"""
        self.kuzu = kuzu_conn

    def init_schema(self) -> None:
        """Initialize KuzuDB schema for departments"""
        # Create node tables
        self.kuzu.execute("""
            CREATE NODE TABLE IF NOT EXISTS Department (
                id INT64 PRIMARY KEY,
                name STRING,
                slug STRING,
                status STRING,
                created_at STRING
            )
        """)

        self.kuzu.execute("""
            CREATE NODE TABLE IF NOT EXISTS Agent (
                id INT64 PRIMARY KEY,
                slug STRING,
                name STRING,
                role_type STRING,
                status STRING
            )
        """)

        self.kuzu.execute("""
            CREATE NODE TABLE IF NOT EXISTS Team (
                id INT64 PRIMARY KEY,
                name STRING,
                slug STRING,
                department_id INT64,
                status STRING
            )
        """)

        # Create relationship tables
        self.kuzu.execute("""
            CREATE REL TABLE IF NOT EXISTS HAS_AGENT (
                FROM Department TO Agent,
                role STRING,
                joined_at STRING
            )
        """)

        self.kuzu.execute("""
            CREATE REL TABLE IF NOT EXISTS TEAM_HAS_AGENT (
                FROM Team TO Agent,
                role STRING,
                joined_at STRING
            )
        """)

        self.kuzu.execute("""
            CREATE REL TABLE IF NOT EXISTS HAS_CHILD_DEPT (
                FROM Department TO Department,
                relation_type STRING,
                created_at STRING
            )
        """)

        self.kuzu.execute("""
            CREATE REL TABLE IF NOT EXISTS RELATED_TO (
                FROM Department TO Department,
                relation_type STRING,
                description STRING,
                created_at STRING
            )
        """)

        self.kuzu.execute("""
            CREATE REL TABLE IF NOT EXISTS HAS_TEAM (
                FROM Department TO Team,
                created_at STRING
            )
        """)

    def sync_from_sqlite(self, sqlite_conn: sqlite3.Connection) -> None:
        """Sync departments, agents, teams from SQLite to KuzuDB"""
        cursor = sqlite_conn.cursor()

        # Sync departments
        cursor.execute('SELECT id, name, slug, status, created_at FROM departments')
        for row in cursor.fetchall():
            dept_id, name, slug, status, created_at = row
            self.kuzu.execute(
                'CREATE (:Department {id: $id, name: $name, slug: $slug, status: $status, created_at: $created_at})',
                {'id': int(dept_id), 'name': name, 'slug': slug, 'status': status, 'created_at': created_at}
            )

        # Sync agents
        cursor.execute('SELECT id, slug, name, role_type, status FROM agents')
        for row in cursor.fetchall():
            agent_id, slug, name, role_type, status = row
            self.kuzu.execute(
                'CREATE (:Agent {id: $id, slug: $slug, name: $name, role_type: $role_type, status: $status})',
                {'id': int(agent_id), 'slug': slug, 'name': name, 'role_type': role_type, 'status': status}
            )

        # Sync teams
        cursor.execute('SELECT id, name, slug, department_id, status FROM teams')
        for row in cursor.fetchall():
            team_id, name, slug, dept_id, status = row
            self.kuzu.execute(
                'CREATE (:Team {id: $id, name: $name, slug: $slug, department_id: $dept_id, status: $status})',
                {'id': int(team_id), 'name': name, 'slug': slug, 'dept_id': int(dept_id), 'status': status}
            )

        # Sync HAS_AGENT relationships
        cursor.execute(
            'SELECT department_id, agent_id, role, joined_at FROM department_agents WHERE left_at IS NULL'
        )
        for row in cursor.fetchall():
            dept_id, agent_id, role, joined_at = row
            self.kuzu.execute(
                '''
                MATCH (d:Department {id: $dept_id}), (a:Agent {id: $agent_id})
                CREATE (d)-[rel:HAS_AGENT {role: $role, joined_at: $joined_at}]->(a)
                ''',
                {'dept_id': int(dept_id), 'agent_id': int(agent_id), 'role': role, 'joined_at': joined_at}
            )

        # Sync TEAM_HAS_AGENT relationships
        cursor.execute('SELECT team_id, agent_id, role, joined_at FROM team_x_agents')
        for row in cursor.fetchall():
            team_id, agent_id, role, joined_at = row
            self.kuzu.execute(
                '''
                MATCH (t:Team {id: $team_id}), (a:Agent {id: $agent_id})
                CREATE (t)-[rel:TEAM_HAS_AGENT {role: $role, joined_at: $joined_at}]->(a)
                ''',
                {'team_id': int(team_id), 'agent_id': int(agent_id), 'role': role, 'joined_at': joined_at}
            )

        # Sync HAS_CHILD_DEPT relationships (from parent_id in departments)
        cursor.execute('SELECT id, parent_id FROM departments WHERE parent_id IS NOT NULL')
        for row in cursor.fetchall():
            dept_id, parent_id = row
            self.kuzu.execute(
                '''
                MATCH (parent:Department {id: $parent_id}), (child:Department {id: $dept_id})
                CREATE (parent)-[rel:HAS_CHILD_DEPT {relation_type: 'parent', created_at: $now}]->(child)
                ''',
                {'parent_id': int(parent_id), 'dept_id': int(dept_id), 'now': ''}
            )

        # Sync RELATED_TO relationships
        cursor.execute(
            'SELECT dept_a_id, dept_b_id, relation_type, description, created_at FROM department_relations'
        )
        for row in cursor.fetchall():
            dept_a_id, dept_b_id, relation_type, description, created_at = row
            self.kuzu.execute(
                '''
                MATCH (a:Department {id: $dept_a_id}), (b:Department {id: $dept_b_id})
                CREATE (a)-[rel:RELATED_TO {relation_type: $type, description: $desc, created_at: $created}]->(b)
                ''',
                {'dept_a_id': int(dept_a_id), 'dept_b_id': int(dept_b_id), 'type': relation_type,
                 'desc': description, 'created': created_at}
            )

        # Sync HAS_TEAM relationships
        cursor.execute('SELECT id, department_id FROM teams')
        for row in cursor.fetchall():
            team_id, dept_id = row
            self.kuzu.execute(
                '''
                MATCH (d:Department {id: $dept_id}), (t:Team {id: $team_id})
                CREATE (d)-[rel:HAS_TEAM {created_at: $now}]->(t)
                ''',
                {'dept_id': int(dept_id), 'team_id': int(team_id), 'now': ''}
            )

    def get_department_agents(self, dept_id: int) -> list[dict]:
        """Get all agents in a department"""
        result = self.kuzu.execute(
            '''
            MATCH (d:Department {id: $dept_id})-[rel:HAS_AGENT]->(a:Agent)
            RETURN a.id, a.slug, a.name, a.role_type, rel.role, rel.joined_at
            ''',
            {'dept_id': int(dept_id)}
        )
        agents = []
        while result.has_next():
            row = result.get_next()
            agents.append({
                'agent_id': int(row[0]),
                'slug': row[1],
                'name': row[2],
                'role_type': row[3],
                'role': row[4],
                'joined_at': row[5]
            })
        return agents

    def get_department_hierarchy(self, dept_id: int) -> list[dict]:
        """Get all descendant departments recursively"""
        result = self.kuzu.execute(
            '''
            MATCH (d:Department {id: $dept_id})-[:HAS_CHILD_DEPT*]->(child:Department)
            RETURN child.id, child.name, child.slug, child.status
            ''',
            {'dept_id': int(dept_id)}
        )
        descendants = []
        while result.has_next():
            row = result.get_next()
            descendants.append({
                'id': int(row[0]),
                'name': row[1],
                'slug': row[2],
                'status': row[3]
            })
        return descendants

    def get_department_relations(self, dept_id: int) -> list[dict]:
        """Get related departments"""
        result = self.kuzu.execute(
            '''
            MATCH (d:Department {id: $dept_id})-[rel:RELATED_TO]->(related:Department)
            RETURN related.id, related.name, related.slug, rel.relation_type, rel.description
            ''',
            {'dept_id': int(dept_id)}
        )
        relations = []
        while result.has_next():
            row = result.get_next()
            relations.append({
                'related_id': int(row[0]),
                'name': row[1],
                'slug': row[2],
                'relation_type': row[3],
                'description': row[4]
            })
        return relations

    def detect_circular_parent_assignment(self, dept_id: int, parent_id: int) -> bool:
        """Detect if assigning parent_id to dept_id would create a cycle"""
        if dept_id == parent_id:
            return True

        # Check if parent_id is a descendant of dept_id
        result = self.kuzu.execute(
            '''
            MATCH (d:Department {id: $dept_id})-[:HAS_CHILD_DEPT*]->(child:Department)
            WHERE child.id = $parent_id
            RETURN COUNT(*) as cnt
            ''',
            {'dept_id': int(dept_id), 'parent_id': int(parent_id)}
        )

        if result.has_next():
            row = result.get_next()
            return int(row[0]) > 0
        return False

    def get_agent_departments(self, agent_id: int) -> list[dict]:
        """Get all departments an agent belongs to"""
        result = self.kuzu.execute(
            '''
            MATCH (a:Agent {id: $agent_id})<-[rel:HAS_AGENT]-(d:Department)
            RETURN d.id, d.name, d.slug, rel.role, rel.joined_at
            ''',
            {'agent_id': int(agent_id)}
        )
        departments = []
        while result.has_next():
            row = result.get_next()
            departments.append({
                'dept_id': int(row[0]),
                'name': row[1],
                'slug': row[2],
                'role': row[3],
                'joined_at': row[4]
            })
        return departments

    def add_agent_to_department(self, dept_id: int, agent_id: int, role: str, joined_at: str) -> None:
        """Add HAS_AGENT relationship"""
        self.kuzu.execute(
            '''
            MATCH (d:Department {id: $dept_id}), (a:Agent {id: $agent_id})
            CREATE (d)-[rel:HAS_AGENT {role: $role, joined_at: $joined_at}]->(a)
            ''',
            {'dept_id': int(dept_id), 'agent_id': int(agent_id), 'role': role, 'joined_at': joined_at}
        )

    def remove_agent_from_department(self, dept_id: int, agent_id: int) -> None:
        """Remove HAS_AGENT relationship"""
        self.kuzu.execute(
            '''
            MATCH (d:Department {id: $dept_id})-[rel:HAS_AGENT]->(a:Agent {id: $agent_id})
            DELETE rel
            ''',
            {'dept_id': int(dept_id), 'agent_id': int(agent_id)}
        )
