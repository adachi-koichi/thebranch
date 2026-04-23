"""KuzuDB GraphRepository for workflow DAG management"""
from pathlib import Path
from workflow.repositories.kuzu_connection import KuzuConnection
import kuzu


class WorkflowGraphRepository:
    """KuzuDB graph operations for workflow DAG"""

    def __init__(self, db_path: str | Path = None):
        """Initialize with KuzuDB connection"""
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'workflow_graph.kuzu'
        self.kuzu = KuzuConnection(db_path)

    def initialize_schema(self) -> None:
        """Initialize KuzuDB schema for workflow tasks and relationships"""
        self.kuzu.execute("""
            CREATE NODE TABLE IF NOT EXISTS WorkflowTask (
                task_id STRING PRIMARY KEY,
                name STRING,
                description STRING,
                node_type STRING,
                estimated_duration_minutes INT64,
                priority STRING,
                role_hint STRING,
                status STRING,
                workflow_instance_id STRING
            )
        """)

        self.kuzu.execute("""
            CREATE NODE TABLE IF NOT EXISTS WorkflowMilestone (
                milestone_id STRING PRIMARY KEY,
                name STRING,
                description STRING,
                status STRING,
                workflow_instance_id STRING
            )
        """)

        self.kuzu.execute("""
            CREATE REL TABLE IF NOT EXISTS workflow_depends_on (
                FROM WorkflowTask TO WorkflowTask,
                condition STRING,
                dep_type STRING
            )
        """)

        self.kuzu.execute("""
            CREATE REL TABLE IF NOT EXISTS workflow_blocks (
                FROM WorkflowTask TO WorkflowTask,
                reason STRING
            )
        """)

        self.kuzu.execute("""
            CREATE REL TABLE IF NOT EXISTS workflow_triggers (
                FROM WorkflowTask TO WorkflowTask,
                trigger_condition STRING
            )
        """)

    def save_workflow_dag(self, generation_id: str, workflow: dict) -> bool:
        """
        Save workflow DAG from NLP service to KuzuDB.

        Args:
            generation_id: Unique workflow generation identifier
            workflow: Dictionary with structure:
                {
                    'name': str,
                    'nodes': [{'task_id', 'name', 'type', 'description',
                               'estimated_duration_minutes', 'priority', 'role_hint'}, ...],
                    'edges': [{'from', 'to', 'type', 'condition'}, ...]
                }

        Returns:
            True on success, False on error
        """
        try:
            nodes = workflow.get('nodes', [])
            edges = workflow.get('edges', [])

            for node in nodes:
                task_id = node['task_id']
                namespaced_task_id = f"{generation_id}:{task_id}"

                params = {
                    'task_id': namespaced_task_id,
                    'name': node.get('name', ''),
                    'description': node.get('description'),
                    'node_type': node.get('type'),
                    'estimated_duration_minutes': int(node.get('estimated_duration_minutes', 0)),
                    'priority': node.get('priority'),
                    'role_hint': node.get('role_hint'),
                    'workflow_instance_id': generation_id
                }

                try:
                    self.kuzu.execute(
                        """
                        CREATE (:WorkflowTask {
                            task_id: $task_id,
                            name: $name,
                            description: $description,
                            node_type: $node_type,
                            estimated_duration_minutes: $estimated_duration_minutes,
                            priority: $priority,
                            role_hint: $role_hint,
                            workflow_instance_id: $workflow_instance_id
                        })
                        """,
                        params
                    )
                except kuzu.RuntimeError as e:
                    if 'already exists' not in str(e):
                        raise

            for edge in edges:
                from_task_id = f"{generation_id}:{edge['from']}"
                to_task_id = f"{generation_id}:{edge['to']}"
                edge_type = edge.get('type', 'depends_on')
                condition = edge.get('condition')

                if edge_type == 'depends_on':
                    params = {
                        'from_id': from_task_id,
                        'to_id': to_task_id,
                        'condition': condition,
                        'dep_type': 'depends_on'
                    }
                    try:
                        self.kuzu.execute(
                            """
                            MATCH (from:WorkflowTask {task_id: $from_id}),
                                  (to:WorkflowTask {task_id: $to_id})
                            CREATE (from)-[rel:workflow_depends_on {
                                condition: $condition,
                                dep_type: $dep_type
                            }]->(to)
                            """,
                            params
                        )
                    except kuzu.RuntimeError as e:
                        if 'already exists' not in str(e):
                            raise

                elif edge_type == 'blocks':
                    params = {
                        'from_id': from_task_id,
                        'to_id': to_task_id,
                        'reason': condition
                    }
                    try:
                        self.kuzu.execute(
                            """
                            MATCH (from:WorkflowTask {task_id: $from_id}),
                                  (to:WorkflowTask {task_id: $to_id})
                            CREATE (from)-[rel:workflow_blocks {
                                reason: $reason
                            }]->(to)
                            """,
                            params
                        )
                    except kuzu.RuntimeError as e:
                        if 'already exists' not in str(e):
                            raise

                elif edge_type == 'triggers':
                    params = {
                        'from_id': from_task_id,
                        'to_id': to_task_id,
                        'trigger_condition': condition
                    }
                    try:
                        self.kuzu.execute(
                            """
                            MATCH (from:WorkflowTask {task_id: $from_id}),
                                  (to:WorkflowTask {task_id: $to_id})
                            CREATE (from)-[rel:workflow_triggers {
                                trigger_condition: $trigger_condition
                            }]->(to)
                            """,
                            params
                        )
                    except kuzu.RuntimeError as e:
                        if 'already exists' not in str(e):
                            raise

            return True
        except Exception as e:
            raise

    def get_workflow_tasks(self, workflow_instance_id: str) -> list[dict]:
        """Get all tasks in a workflow by generation_id"""
        result = self.kuzu.execute(
            """
            MATCH (t:WorkflowTask {workflow_instance_id: $workflow_instance_id})
            RETURN t.task_id, t.name, t.description, t.node_type,
                   t.estimated_duration_minutes, t.priority, t.role_hint, t.status
            """,
            {'workflow_instance_id': workflow_instance_id}
        )

        tasks = []
        while result.has_next():
            row = result.get_next()
            task_id_full = row[0]
            task_id = task_id_full.split(':', 1)[1] if ':' in task_id_full else task_id_full

            tasks.append({
                'task_id': task_id,
                'task_id_full': task_id_full,
                'name': row[1],
                'description': row[2],
                'node_type': row[3],
                'estimated_duration_minutes': int(row[4]) if row[4] else 0,
                'priority': row[5],
                'role_hint': row[6],
                'status': row[7]
            })
        return tasks

    def check_cycle(self, workflow_instance_id: str) -> list[str]:
        """
        Detect cycles in workflow DAG.

        Returns:
            List of task IDs involved in cycles (empty if no cycles)
        """
        result = self.kuzu.execute(
            """
            MATCH (t:WorkflowTask {workflow_instance_id: $workflow_instance_id})
                  -[:workflow_depends_on*2..]->(t:WorkflowTask)
            RETURN DISTINCT t.task_id
            """,
            {'workflow_instance_id': workflow_instance_id}
        )

        cycles = []
        while result.has_next():
            row = result.get_next()
            task_id_full = row[0]
            task_id = task_id_full.split(':', 1)[1] if ':' in task_id_full else task_id_full
            cycles.append(task_id)

        return cycles

    def get_dependencies(self, task_id_full: str) -> list[dict]:
        """
        Get all tasks that the given task depends on.

        Args:
            task_id_full: Full task ID (with workflow_instance_id prefix)

        Returns:
            List of dependent task information
        """
        result = self.kuzu.execute(
            """
            MATCH (from:WorkflowTask {task_id: $task_id})
                  -[rel:workflow_depends_on]->(to:WorkflowTask)
            RETURN to.task_id, to.name, to.priority, to.estimated_duration_minutes,
                   rel.condition, rel.dep_type
            """,
            {'task_id': task_id_full}
        )

        dependencies = []
        while result.has_next():
            row = result.get_next()
            task_id_full = row[0]
            task_id = task_id_full.split(':', 1)[1] if ':' in task_id_full else task_id_full

            dependencies.append({
                'task_id': task_id,
                'task_id_full': task_id_full,
                'name': row[1],
                'priority': row[2],
                'estimated_duration_minutes': int(row[3]) if row[3] else 0,
                'condition': row[4],
                'dep_type': row[5]
            })
        return dependencies

    def get_blocking_tasks(self, task_id_full: str) -> list[dict]:
        """Get all tasks that block the given task"""
        result = self.kuzu.execute(
            """
            MATCH (from:WorkflowTask)
                  -[rel:workflow_blocks]->(to:WorkflowTask {task_id: $task_id})
            RETURN from.task_id, from.name, rel.reason
            """,
            {'task_id': task_id_full}
        )

        blockers = []
        while result.has_next():
            row = result.get_next()
            task_id_full = row[0]
            task_id = task_id_full.split(':', 1)[1] if ':' in task_id_full else task_id_full

            blockers.append({
                'task_id': task_id,
                'task_id_full': task_id_full,
                'name': row[1],
                'reason': row[2]
            })
        return blockers

    def close(self):
        """Close KuzuDB connection"""
        self.kuzu.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
