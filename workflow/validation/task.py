"""Task validation logic"""

from typing import TYPE_CHECKING
import logging

from workflow.exceptions import CircularDependencyError, ValidationError

if TYPE_CHECKING:
    from workflow.repositories.task import TaskRepository

logger = logging.getLogger(__name__)


class TaskValidator:
    """Validate task definitions and dependencies"""

    def __init__(self, task_repo: 'TaskRepository') -> None:
        self.task_repo = task_repo

    def validate_no_cycles(self, instance_id: int) -> None:
        """
        Validate task dependency DAG has no cycles.

        Uses DFS to detect cycles in the task dependency graph.

        Args:
            instance_id: Workflow instance id

        Raises:
            CircularDependencyError: If cycle detected
        """
        # Get all tasks and dependencies for instance
        tasks = self.task_repo.get_instance_tasks(instance_id)
        task_map = {task.id: task for task in tasks}

        if not tasks:
            return  # No tasks, no cycles

        # Build adjacency list from dependencies
        graph: dict[int, list[int]] = {task.id: [] for task in tasks}
        dependencies = self.task_repo.get_task_dependencies(instance_id)

        for dep in dependencies:
            # successor depends on predecessor
            graph[dep.predecessor_id].append(dep.successor_id)

        # Check for cycles using DFS
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[int, int] = {task.id: WHITE for task in tasks}
        parent: dict[int, int | None] = {task.id: None for task in tasks}

        def dfs(node_id: int, path: list[int]) -> None:
            if color[node_id] == GRAY:
                # Found cycle: back edge
                cycle_start = next(
                    (i for i, n in enumerate(path) if n == node_id), -1
                )
                if cycle_start >= 0:
                    cycle = path[cycle_start:] + [node_id]
                    logger.error(f"Cycle detected: {cycle}")
                    raise CircularDependencyError(cycle)

            if color[node_id] == BLACK:
                return

            color[node_id] = GRAY
            path.append(node_id)

            for neighbor in graph[node_id]:
                dfs(neighbor, path)

            path.pop()
            color[node_id] = BLACK

        # Check from all unvisited nodes
        for task_id in graph:
            if color[task_id] == WHITE:
                try:
                    dfs(task_id, [])
                except CircularDependencyError:
                    raise

    def validate_task_dependency_reference(
        self,
        instance_id: int,
        predecessor_id: int,
        successor_id: int,
    ) -> None:
        """
        Validate both tasks exist in instance.

        Args:
            instance_id: Workflow instance id
            predecessor_id: Task id that precedes
            successor_id: Task id that depends

        Raises:
            ValidationError: If either task doesn't exist
        """
        tasks = self.task_repo.get_instance_tasks(instance_id)
        task_ids = {task.id for task in tasks}

        if predecessor_id not in task_ids:
            raise ValidationError(
                f"Predecessor task {predecessor_id} not found in instance {instance_id}",
                details={
                    'instance_id': instance_id,
                    'predecessor_id': predecessor_id,
                },
            )

        if successor_id not in task_ids:
            raise ValidationError(
                f"Successor task {successor_id} not found in instance {instance_id}",
                details={
                    'instance_id': instance_id,
                    'successor_id': successor_id,
                },
            )

    def validate_task_properties(
        self,
        title: str,
        assignee: str,
        phase: str,
        priority: int,
    ) -> None:
        """
        Validate task properties.

        Args:
            title: Task title
            assignee: Specialist email
            phase: Phase key
            priority: Priority (1-5)

        Raises:
            ValidationError: If any property invalid
        """
        # Validate title
        if not title or len(title) > 1024:
            raise ValidationError(
                f"Invalid task title: '{title}'",
                details={'title': title},
            )

        # Validate assignee (email)
        if not assignee or '@' not in assignee:
            raise ValidationError(
                f"Invalid assignee email: '{assignee}'",
                details={'assignee': assignee},
            )

        if len(assignee) > 255:
            raise ValidationError(
                f"Assignee email too long: {len(assignee)} chars",
                details={'assignee': assignee},
            )

        # Validate phase
        if not phase or len(phase) > 100:
            raise ValidationError(
                f"Invalid phase: '{phase}'",
                details={'phase': phase},
            )

        # Validate priority
        if not (1 <= priority <= 5):
            raise ValidationError(
                f"Invalid priority: {priority} (must be 1-5)",
                details={'priority': priority},
            )
