from collections import defaultdict, deque
from workflow.repositories.base import BaseRepository


class GraphRepository(BaseRepository):
    """Data access for workflow graph operations (cycle detection, etc)"""

    def check_cycles(self, instance_id: int) -> list[int] | None:
        """
        Detect circular dependencies in task graph.

        Returns:
            List of task IDs forming a cycle, or None if no cycle exists
        """
        query = '''
            SELECT predecessor_id, successor_id
            FROM task_dependencies
            WHERE predecessor_id IN (SELECT id FROM dev_tasks WHERE workflow_instance_id = ?)
        '''
        rows = self.execute_all(query, (instance_id,))

        if not rows:
            return None

        graph = defaultdict(list)
        for row in rows:
            graph[row['predecessor_id']].append(row['successor_id'])

        cycle = self._find_cycle(graph)
        return cycle

    def get_task_dependencies(self, instance_id: int) -> list[tuple[int, int, str]]:
        """Get all task dependencies for instance as (predecessor_id, successor_id, dep_type)"""
        query = '''
            SELECT predecessor_id, successor_id, dep_type
            FROM task_dependencies
            WHERE predecessor_id IN (SELECT id FROM dev_tasks WHERE workflow_instance_id = ?)
            ORDER BY predecessor_id, successor_id
        '''
        rows = self.execute_all(query, (instance_id,))
        return [(row['predecessor_id'], row['successor_id'], row['dep_type']) for row in rows]

    def get_predecessors(self, task_id: int) -> list[int]:
        """Get all direct predecessors of a task"""
        query = '''
            SELECT predecessor_id FROM task_dependencies
            WHERE successor_id = ?
        '''
        rows = self.execute_all(query, (task_id,))
        return [row['predecessor_id'] for row in rows]

    def get_successors(self, task_id: int) -> list[int]:
        """Get all direct successors of a task"""
        query = '''
            SELECT successor_id FROM task_dependencies
            WHERE predecessor_id = ?
        '''
        rows = self.execute_all(query, (task_id,))
        return [row['successor_id'] for row in rows]

    def get_reachable_tasks(self, task_id: int) -> set[int]:
        """Get all tasks reachable from given task (DFS)"""
        visited = set()
        stack = [task_id]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            successors = self.get_successors(current)
            stack.extend(successors)

        return visited

    @staticmethod
    def _find_cycle(graph: dict[int, list[int]]) -> list[int] | None:
        """
        Find a cycle in directed graph using DFS.

        Returns:
            List of node IDs forming cycle, or None if no cycle
        """
        visited = set()
        rec_stack = set()
        parent = {}

        def dfs(node: int, path: list[int]) -> list[int] | None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    result = dfs(neighbor, path[:])
                    if result:
                        return result
                elif neighbor in rec_stack:
                    cycle_start_idx = path.index(neighbor)
                    return path[cycle_start_idx:] + [neighbor]

            rec_stack.remove(node)
            return None

        for node in graph:
            if node not in visited:
                result = dfs(node, [])
                if result:
                    return result

        return None
