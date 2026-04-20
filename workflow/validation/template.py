"""Template validation logic"""

from typing import TYPE_CHECKING
import logging

from workflow.exceptions import ValidationError, CircularDependencyError

if TYPE_CHECKING:
    from workflow.repositories.template import TemplateRepository

logger = logging.getLogger(__name__)


class TemplateValidator:
    """Validate template structure and constraints"""

    def __init__(self, template_repo: 'TemplateRepository') -> None:
        self.template_repo = template_repo

    def validate_phase(
        self,
        template_id: int,
        phase_key: str,
        specialist_type: str,
        phase_order: int,
    ) -> None:
        """
        Validate phase addition.

        Raises:
            ValidationError: If phase_key already exists
            ValidationError: If specialist_type is invalid
            ValidationError: If phase_order conflicts
        """
        # Valid specialist types
        valid_types = {'pm', 'engineer', 'qa', 'devops'}
        if specialist_type not in valid_types:
            raise ValidationError(
                f"Invalid specialist_type: {specialist_type}",
                details={'valid_types': valid_types},
            )

        # Check phase_key uniqueness within template
        existing_phases = self.template_repo.get_phases(template_id)
        if any(p.phase_key == phase_key for p in existing_phases):
            raise ValidationError(
                f"Phase key '{phase_key}' already exists in template {template_id}",
                details={'template_id': template_id, 'phase_key': phase_key},
            )

        # Check phase_order validity
        if phase_order < 1:
            raise ValidationError(
                f"phase_order must be >= 1, got {phase_order}",
                details={'phase_order': phase_order},
            )

    def validate_task_def(
        self,
        phase_id: int,
        task_key: str,
        depends_on_key: str | None,
    ) -> None:
        """
        Validate task definition.

        Raises:
            ValidationError: If task_key already exists
            ValidationError: If depends_on_key references non-existent task
        """
        # Get all tasks in phase
        tasks = self.template_repo.get_tasks_for_phase(phase_id)

        # Check task_key uniqueness
        if any(t.task_key == task_key for t in tasks):
            raise ValidationError(
                f"Task key '{task_key}' already exists in phase {phase_id}",
                details={'phase_id': phase_id, 'task_key': task_key},
            )

        # Validate dependency reference
        if depends_on_key:
            if not any(t.task_key == depends_on_key for t in tasks):
                raise ValidationError(
                    f"Referenced task '{depends_on_key}' not found in phase {phase_id}",
                    details={
                        'phase_id': phase_id,
                        'depends_on_key': depends_on_key,
                    },
                )

    def validate_template_complete(self, template_id: int) -> None:
        """
        Validate template is ready for publishing.

        Raises:
            ValidationError: If no phases or tasks
            ValidationError: If any phase has no tasks
            CircularDependencyError: If circular dependency exists
        """
        phases = self.template_repo.get_phases(template_id)

        # Check template has phases
        if not phases:
            raise ValidationError(
                f"Template {template_id} has no phases",
                details={'template_id': template_id},
            )

        # Check all phases have tasks
        for phase in phases:
            tasks = self.template_repo.get_tasks_for_phase(phase.id)
            if not tasks:
                raise ValidationError(
                    f"Phase '{phase.phase_key}' (id={phase.id}) has no tasks",
                    details={'template_id': template_id, 'phase_id': phase.id},
                )

        # Validate no circular dependencies within phases
        for phase in phases:
            self._check_intra_phase_cycles(phase.id)

    def _check_intra_phase_cycles(self, phase_id: int) -> None:
        """Check for circular dependencies within a phase"""
        tasks = self.template_repo.get_tasks_for_phase(phase_id)

        # Build dependency graph
        graph: dict[str, str | None] = {
            task.task_key: task.depends_on_key for task in tasks
        }

        # Check for cycles using DFS
        for task in tasks:
            visited: set[str] = set()
            path: list[str] = []

            def dfs(key: str) -> None:
                if key in visited:
                    # Found a cycle
                    cycle_start = path.index(key) if key in path else -1
                    if cycle_start >= 0:
                        cycle = path[cycle_start:] + [key]
                        raise CircularDependencyError(
                            [t for t in cycle]
                        )
                    return

                if key is None:
                    return

                visited.add(key)
                path.append(key)

                next_key = graph.get(key)
                if next_key:
                    dfs(next_key)

                path.pop()

            dfs(task.task_key)
