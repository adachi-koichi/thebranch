"""Task generation and dependency management service"""

from typing import TYPE_CHECKING
from datetime import datetime
import logging
import re

from workflow.models import DevTask, Phase
from workflow.exceptions import (
    InstanceNotFoundError,
    ValidationError,
)

if TYPE_CHECKING:
    from workflow.repositories.task import TaskRepository
    from workflow.repositories.template import TemplateRepository
    from workflow.repositories.instance import InstanceRepository
    from workflow.models.specialist import Agent
    from workflow.validation.task import TaskValidator

logger = logging.getLogger(__name__)


class TaskGenerationService:
    """
    Auto-generate tasks from template.

    Responsibilities:
    - Generate tasks for all phases
    - Apply placeholders
    - Create inter-phase dependencies
    - Create intra-phase dependencies
    - Ensure idempotency
    """

    def __init__(
        self,
        task_repo: 'TaskRepository',
        template_repo: 'TemplateRepository',
        instance_repo: 'InstanceRepository',
        validator: 'TaskValidator',
    ) -> None:
        self.task_repo = task_repo
        self.template_repo = template_repo
        self.instance_repo = instance_repo
        self.validator = validator

    # ===== MAIN GENERATION =====

    def generate_tasks_for_instance(
        self,
        instance_id: int,
        template_id: int,
    ) -> int:
        """
        Generate all tasks for instance from template.

        Algorithm:
        1. Check idempotency (no existing tasks)
        2. Get phases sorted by phase_order
        3. For each phase:
           a. Get task definitions
           b. Get assigned specialist
           c. Create tasks with placeholders resolved
           d. Create intra-phase dependencies
        4. Create inter-phase dependencies
        5. Validate dependency DAG (no cycles)

        Args:
            instance_id: Target workflow instance
            template_id: Source template

        Returns:
            Total number of tasks generated

        Raises:
            InstanceNotFoundError
            TemplateNotFoundError
            ValidationError: If tasks already generated
            CircularDependencyError: If DAG validation fails
            DatabaseError: If insertion fails
        """
        from workflow.exceptions import TemplateNotFoundError

        # Check idempotency
        existing = self.task_repo.count_instance_tasks(instance_id)
        if existing > 0:
            logger.info(f"Tasks already generated for instance {instance_id}")
            return existing

        instance = self.instance_repo.get_instance(instance_id)
        if not instance:
            raise InstanceNotFoundError(f"Instance {instance_id} not found")

        # Get template
        template = self.template_repo.get_template(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        # Get phases sorted
        phases = self.template_repo.get_phases(template_id)

        total_generated = 0
        phase_task_map: dict[str, list[DevTask]] = {}

        try:
            # For each phase
            for phase in phases:
                # Get specialist assigned to this phase
                specialist = self.instance_repo.get_phase_specialist(
                    instance_id, phase.id
                )

                # Get task definitions for this phase
                task_defs = self.template_repo.get_tasks_for_phase(phase.id)

                # Generate tasks
                phase_tasks: list[DevTask] = []
                for task_def in task_defs:
                    task = self._create_task_from_def(
                        instance_id=instance_id,
                        phase_key=phase.phase_key,
                        task_def=task_def,
                        specialist=specialist,
                        phase_label=phase.phase_label,
                        workflow_name=instance.name,
                    )
                    phase_tasks.append(task)
                    total_generated += 1

                phase_task_map[phase.phase_key] = phase_tasks

                # Create intra-phase dependencies
                self._create_intra_phase_dependencies(
                    phase=phase,
                    task_defs=task_defs,
                    phase_tasks=phase_tasks,
                )

            # Create inter-phase dependencies
            self._create_inter_phase_dependencies(
                phases=phases,
                phase_task_map=phase_task_map,
            )

            # Validate DAG
            self.validator.validate_no_cycles(instance_id)

            logger.info(f"Generated {total_generated} tasks for instance {instance_id}")
            return total_generated

        except Exception as e:
            # Cleanup on error
            self.task_repo.delete_instance_tasks(instance_id)
            logger.error(f"Task generation failed, rolled back: {e}")
            raise

    # ===== TASK CREATION =====

    def _create_task_from_def(
        self,
        instance_id: int,
        phase_key: str,
        task_def,
        specialist: 'Agent',
        phase_label: str,
        workflow_name: str,
    ) -> DevTask:
        """
        Create single task with placeholders resolved.

        Placeholders:
        - {phase_label}: Phase display name
        - {phase_key}: Phase key
        - {specialist_name}: Assigned specialist name
        - {specialist_email}: Specialist email
        - {workflow_name}: Instance name
        - {current_date}: ISO format date
        """
        # Resolve placeholders
        context = {
            'phase_label': phase_label,
            'phase_key': phase_key,
            'specialist_name': specialist.name,
            'specialist_email': specialist.email,
            'workflow_name': workflow_name,
            'current_date': datetime.now().isoformat(),
        }

        resolved_title = self._apply_placeholders(
            task_def.task_title,
            context,
        )
        resolved_description = self._apply_placeholders(
            task_def.task_description or '',
            context,
        )

        # Create task (initial status: blocked)
        task = self.task_repo.create_task(
            title=resolved_title,
            description=resolved_description,
            assignee=specialist.email,
            phase=phase_key,
            workflow_instance_id=instance_id,
            wf_node_key=phase_key,
            status='blocked',
            priority=task_def.priority,
            estimated_hours=task_def.estimated_hours,
        )

        return task

    def _apply_placeholders(
        self,
        template_text: str,
        context: dict[str, str],
    ) -> str:
        """
        Replace {placeholders} in text.

        Args:
            template_text: Text with {placeholders}
            context: {placeholder_name → value}

        Returns:
            Text with placeholders replaced

        Note:
        - Missing placeholders are logged as warning
        - Unresolved placeholders remain in text
        """
        result = template_text

        for placeholder, value in context.items():
            result = result.replace(f'{{{placeholder}}}', str(value))

        # Warn about unresolved
        unresolved = re.findall(r'\{[^}]+\}', result)
        if unresolved:
            logger.warning(f"Unresolved placeholders: {unresolved}")

        return result

    # ===== DEPENDENCIES =====

    def _create_intra_phase_dependencies(
        self,
        phase: Phase,
        task_defs: list,
        phase_tasks: list[DevTask],
    ) -> None:
        """
        Create task dependencies within same phase.

        Algorithm:
        1. For each task with depends_on_key
        2. Find referenced predecessor task_def
        3. Map to corresponding phase_task
        4. Insert dependency edge
        """
        for task_def in task_defs:
            if not task_def.depends_on_key:
                continue

            # Find predecessor task_def
            pred_def = next(
                (td for td in task_defs if td.task_key == task_def.depends_on_key),
                None,
            )

            if not pred_def:
                logger.warning(
                    f"Predecessor task not found: "
                    f"phase={phase.phase_key}, depends_on={task_def.depends_on_key}"
                )
                continue

            # Find corresponding task objects by task_key
            try:
                task_idx = next(
                    i for i, td in enumerate(task_defs) if td.task_key == task_def.task_key
                )
                pred_idx = next(
                    i for i, td in enumerate(task_defs) if td.task_key == pred_def.task_key
                )

                task = phase_tasks[task_idx]
                pred_task = phase_tasks[pred_idx]

                # Create dependency
                self.task_repo.create_task_dependency(
                    predecessor_id=pred_task.id,
                    successor_id=task.id,
                    dep_type='intra_phase',
                )
            except (ValueError, IndexError) as e:
                logger.error(
                    f"Failed to create intra-phase dependency: {e}"
                )

    def _create_inter_phase_dependencies(
        self,
        phases: list[Phase],
        phase_task_map: dict[str, list[DevTask]],
    ) -> None:
        """
        Create dependencies between phases.

        Rule:
        All tasks in Phase N-1 must complete before Phase N tasks unblock.

        Implementation:
        For each task in Phase N, create edge from all Phase N-1 tasks.
        """
        for i, phase in enumerate(phases):
            if i == 0:
                continue  # No predecessor for first phase

            prev_phase = phases[i - 1]
            curr_tasks = phase_task_map[phase.phase_key]
            prev_tasks = phase_task_map[prev_phase.phase_key]

            # All predecessors → all current tasks
            for curr_task in curr_tasks:
                for prev_task in prev_tasks:
                    self.task_repo.create_task_dependency(
                        predecessor_id=prev_task.id,
                        successor_id=curr_task.id,
                        dep_type='inter_phase',
                    )
