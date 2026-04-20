"""Workflow instance lifecycle management service"""

from typing import TYPE_CHECKING, Any
import logging

from workflow.models import WorkflowInstance, PhaseInstance
from workflow.exceptions import (
    InstanceNotFoundError,
    ValidationError,
    InvalidStateTransitionError,
)

if TYPE_CHECKING:
    from workflow.repositories.instance import InstanceRepository
    from workflow.repositories.template import TemplateRepository
    from workflow.services.task_gen import TaskGenerationService
    from workflow.services.assignment import SpecialistAssignmentService
    from workflow.validation.instance import InstanceValidator

logger = logging.getLogger(__name__)


class WorkflowInstanceService:
    """
    Workflow instance lifecycle management.

    Responsibilities:
    - Instantiate template
    - Manage phase execution
    - Track instance status
    """

    def __init__(
        self,
        instance_repo: 'InstanceRepository',
        template_repo: 'TemplateRepository',
        task_gen_service: 'TaskGenerationService',
        assignment_svc: 'SpecialistAssignmentService',
        validator: 'InstanceValidator',
    ) -> None:
        self.instance_repo = instance_repo
        self.template_repo = template_repo
        self.task_gen_service = task_gen_service
        self.assignment_svc = assignment_svc
        self.validator = validator

    # ===== INSTANTIATE =====

    def instantiate_workflow(
        self,
        template_id: int,
        instance_name: str,
        specialist_assignments: dict[str, str | int],
        context: dict[str, Any] | None = None,
    ) -> WorkflowInstance:
        """
        Instantiate template to workflow instance (5-step process).

        Steps:
        1. Validate template & assignments
        2. Create workflow_instances record
        3. Assign specialists → workflow_instance_specialists
        4. Create phase instances → wf_instance_nodes
        5. Generate tasks → dev_tasks + task_dependencies

        Args:
            template_id: Template to instantiate
            instance_name: Display name for instance
            specialist_assignments: {phase_key → email | agent_id}
            context: Optional custom context (stored as JSON)

        Returns:
            Instantiated WorkflowInstance with status='ready'

        Raises:
            TemplateNotFoundError: If template_id invalid
            ValidationError: If template is not 'published'
            ValidationError: If assignments incomplete or invalid
            SpecialistNotFoundError: If specialist not found
            SpecialistAssignmentError: If specialist type mismatch
            CircularDependencyError: If detected during task generation
            DatabaseError: If transaction fails (full rollback)
        """
        from workflow.exceptions import TemplateNotFoundError

        # Step 1: Validate
        template = self.template_repo.get_template(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        if template.status != 'published':
            raise ValidationError(
                f"Cannot instantiate non-published template (status={template.status})"
            )

        # Validate specialist assignments
        resolved_assignments = (
            self.assignment_svc.validate_and_resolve_assignments(
                template_id=template_id,
                assignments=specialist_assignments,
            )
        )

        # Step 2: Create instance
        instance = self.instance_repo.create_instance(
            template_id=template_id,
            name=instance_name,
            status='pending',
            context=context or {},
        )

        try:
            # Step 3: Assign specialists
            phases = self.template_repo.get_phases(template_id)
            for phase in phases:
                specialist = resolved_assignments[phase.phase_key]
                self.instance_repo.assign_specialist(
                    instance_id=instance.id,
                    phase_id=phase.id,
                    specialist_id=specialist.id,
                    specialist_slug=specialist.email,
                    specialist_name=specialist.name,
                )

            # Step 4: Create phase instances
            for phase in phases:
                self.instance_repo.create_phase_instance(
                    instance_id=instance.id,
                    phase_id=phase.id,
                    phase_key=phase.phase_key,
                    status='waiting',
                )

            # Step 5: Generate tasks
            task_count = self.task_gen_service.generate_tasks_for_instance(
                instance_id=instance.id,
                template_id=template_id,
            )

            # Update status to ready
            instance.status = 'ready'
            self.instance_repo.update_instance(instance)

            logger.info(
                f"Instantiated workflow: {instance.id} "
                f"with {task_count} tasks"
            )
            return instance

        except Exception as e:
            # Rollback on error
            self.instance_repo.delete_instance(instance.id)
            logger.error(f"Rollback instantiation for instance {instance.id}: {e}")
            raise

    # ===== PHASE EXECUTION =====

    def advance_phase(
        self,
        instance_id: int,
        phase_key: str,
    ) -> PhaseInstance:
        """
        Manually advance phase to 'ready' (if all predecessors completed).
        Usually called implicitly via task completion.

        Args:
            instance_id: Workflow instance
            phase_key: Phase to advance

        Returns:
            Updated PhaseInstance with status changed

        Raises:
            InstanceNotFoundError
            PhaseNotFoundError
            InvalidStateTransitionError: If predecessor phases not completed
        """
        from workflow.exceptions import PhaseNotFoundError

        instance = self.instance_repo.get_instance(instance_id)
        if not instance:
            raise InstanceNotFoundError(f"Instance {instance_id} not found")

        phase_instance = self.instance_repo.get_phase_instance(
            instance_id, phase_key
        )
        if not phase_instance:
            raise PhaseNotFoundError(f"Phase {phase_key} not found")

        # Check all predecessor phases completed
        phases = self.template_repo.get_phases(instance.template_id)

        target_phase = next(
            (p for p in phases if p.phase_key == phase_key), None
        )
        if not target_phase:
            raise PhaseNotFoundError(f"Phase {phase_key} not found in template")

        predecessor_phases = [
            p for p in phases if p.phase_order < target_phase.phase_order
        ]

        for pred_phase in predecessor_phases:
            pred_instance = self.instance_repo.get_phase_instance(
                instance_id, pred_phase.phase_key
            )
            if pred_instance.status != 'completed':
                raise InvalidStateTransitionError(
                    f"Cannot advance {phase_key}: "
                    f"predecessor {pred_phase.phase_key} not completed"
                )

        # Advance to ready
        phase_instance.status = 'ready'
        self.instance_repo.update_phase_instance(phase_instance)

        logger.info(
            f"Advanced phase: {phase_key} in instance {instance_id} to ready"
        )
        return phase_instance

    # ===== QUERY =====

    def get_instance(self, instance_id: int) -> WorkflowInstance:
        """Get instance with basic info"""
        instance = self.instance_repo.get_instance(instance_id)
        if not instance:
            raise InstanceNotFoundError(f"Instance {instance_id} not found")
        return instance

    def get_instance_status(
        self,
        instance_id: int,
    ) -> dict[str, Any]:
        """
        Get detailed status including phases and tasks.

        Returns:
            {
                'instance': WorkflowInstance,
                'phases': [PhaseInstance, ...],
                'tasks': [DevTask, ...],
                'progress': {'total': 14, 'completed': 3, 'pct': 21}
            }
        """
        instance = self.get_instance(instance_id)
        phases = self.instance_repo.get_phase_instances(instance_id)
        tasks = self.instance_repo.get_instance_tasks(instance_id)

        completed = sum(1 for t in tasks if t.status == 'completed')
        total = len(tasks)
        pct = int(100 * completed / total) if total > 0 else 0

        return {
            'instance': instance,
            'phases': phases,
            'tasks': tasks,
            'progress': {
                'total': total,
                'completed': completed,
                'pct': pct,
            },
        }

    def list_instances(
        self,
        template_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkflowInstance]:
        """List instances with optional filtering"""
        return self.instance_repo.list_instances(
            template_id=template_id,
            status=status,
            limit=limit,
            offset=offset,
        )
