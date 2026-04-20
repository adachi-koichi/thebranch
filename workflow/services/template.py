"""Template lifecycle management service"""

from typing import TYPE_CHECKING
import logging

from workflow.models import Template, Phase, TaskDef
from workflow.exceptions import (
    TemplateNotFoundError,
    ValidationError,
)

if TYPE_CHECKING:
    from workflow.repositories.template import TemplateRepository
    from workflow.validation.template import TemplateValidator

logger = logging.getLogger(__name__)


class TemplateService:
    """
    Template lifecycle management

    Responsibilities:
    - Create template
    - Add/update phases
    - Add/update tasks
    - Publish template
    - Query templates
    """

    def __init__(
        self,
        template_repo: 'TemplateRepository',
        validator: 'TemplateValidator',
    ) -> None:
        self.template_repo = template_repo
        self.validator = validator

    # ===== CREATE =====

    def create_template(
        self,
        name: str,
        description: str | None = None,
        created_by: str | None = None,
    ) -> Template:
        """
        Create new template in 'draft' status.

        Args:
            name: Template name (required, max 255 chars)
            description: Optional description
            created_by: Creator identifier (email or agent_id)

        Returns:
            Template object with assigned id

        Raises:
            ValidationError: If name is empty or invalid
            DatabaseError: If insertion fails
        """
        # Validate
        if not name or len(name) > 255:
            raise ValidationError(f"Invalid template name: {name}")

        # Create in DB
        template = self.template_repo.create_template(
            name=name,
            description=description,
            created_by=created_by,
            status='draft',
        )

        logger.info(f"Created template: {template.id} ({template.name})")
        return template

    # ===== PHASE MANAGEMENT =====

    def add_phase(
        self,
        template_id: int,
        phase_key: str,
        phase_label: str,
        specialist_type: str,
        phase_order: int,
        is_parallel: bool = False,
    ) -> Phase:
        """
        Add phase to template (must be in 'draft' status).

        Args:
            template_id: Parent template id
            phase_key: Unique identifier within template (e.g., 'planning')
            phase_label: Display name (e.g., 'Planning')
            specialist_type: Required agent type (pm, engineer, qa, devops)
            phase_order: Execution order (1-based)
            is_parallel: If True, can run parallel with previous phase

        Returns:
            Phase object with assigned id

        Raises:
            TemplateNotFoundError: If template_id doesn't exist
            ValidationError: If template is not in 'draft' status
            ValidationError: If phase_key already exists in template
            ValidationError: If phase_order is invalid
            DatabaseError: If insertion fails
        """
        # Get template
        template = self.template_repo.get_template(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        # Validate template is draft
        if template.status != 'draft':
            raise ValidationError(
                f"Cannot add phase to non-draft template (status={template.status})"
            )

        # Validate inputs
        self.validator.validate_phase(
            template_id=template_id,
            phase_key=phase_key,
            specialist_type=specialist_type,
            phase_order=phase_order,
        )

        # Create in DB
        phase = self.template_repo.create_phase(
            template_id=template_id,
            phase_key=phase_key,
            phase_label=phase_label,
            specialist_type=specialist_type,
            phase_order=phase_order,
            is_parallel=is_parallel,
        )

        logger.info(
            f"Added phase: {phase.id} ({phase.phase_key}) to template {template_id}"
        )
        return phase

    # ===== TASK MANAGEMENT =====

    def add_task_to_phase(
        self,
        phase_id: int,
        task_key: str,
        task_title: str,
        task_description: str | None = None,
        depends_on_key: str | None = None,
        priority: int = 1,
        estimated_hours: float | None = None,
        task_order: int = 0,
    ) -> TaskDef:
        """
        Add task definition to phase.

        Args:
            phase_id: Parent phase id
            task_key: Unique identifier within phase (e.g., 'design-arch')
            task_title: Task name (supports {placeholders})
            task_description: Task details (supports {placeholders})
            depends_on_key: Reference to another task_key in same phase (for ordering)
            priority: 1-5 scale
            estimated_hours: Estimated effort
            task_order: Execution order within phase

        Returns:
            TaskDef object with assigned id

        Raises:
            PhaseNotFoundError: If phase_id doesn't exist
            ValidationError: If phase is not in draft status
            ValidationError: If task_key already exists in phase
            ValidationError: If depends_on_key references non-existent task
            ValidationError: If circular dependency detected
            DatabaseError: If insertion fails
        """
        # Get phase
        phase = self.template_repo.get_phase(phase_id)
        if not phase:
            from workflow.exceptions import PhaseNotFoundError
            raise PhaseNotFoundError(f"Phase {phase_id} not found")

        # Get template (for status check)
        template = self.template_repo.get_template(phase.template_id)
        if template.status != 'draft':
            raise ValidationError(
                f"Cannot add task to non-draft template (status={template.status})"
            )

        # Validate inputs
        self.validator.validate_task_def(
            phase_id=phase_id,
            task_key=task_key,
            depends_on_key=depends_on_key,
        )

        # Create in DB
        task = self.template_repo.create_task_def(
            phase_id=phase_id,
            template_id=phase.template_id,
            task_key=task_key,
            task_title=task_title,
            task_description=task_description,
            depends_on_key=depends_on_key,
            priority=priority,
            estimated_hours=estimated_hours,
            task_order=task_order,
        )

        logger.info(
            f"Added task: {task.id} ({task.task_key}) to phase {phase_id}"
        )
        return task

    # ===== PUBLISH =====

    def publish_template(self, template_id: int) -> Template:
        """
        Publish template (transition from 'draft' to 'published').
        No further edits allowed after publishing.

        Args:
            template_id: Template to publish

        Returns:
            Updated template with status='published'

        Raises:
            TemplateNotFoundError: If template_id doesn't exist
            ValidationError: If template is not in 'draft' status
            ValidationError: If template has no phases or tasks
            CircularDependencyError: If circular dependency detected
            DatabaseError: If update fails
        """
        # Get template
        template = self.template_repo.get_template(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        if template.status != 'draft':
            raise ValidationError(
                f"Cannot publish non-draft template (current status={template.status})"
            )

        # Validate template is complete
        self.validator.validate_template_complete(template_id)

        # Update status
        template.status = 'published'
        self.template_repo.update_template(template)

        logger.info(f"Published template: {template_id}")
        return template

    # ===== QUERY =====

    def get_template(self, template_id: int) -> Template:
        """
        Get template with all phases and tasks (denormalized).

        Returns:
            Template with nested phases and tasks

        Raises:
            TemplateNotFoundError
        """
        template = self.template_repo.get_template_with_phases_and_tasks(
            template_id
        )
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        return template

    def list_templates(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Template]:
        """
        List templates with optional filtering.

        Args:
            status: Filter by status ('draft', 'published', 'archived')
            limit: Max results
            offset: Pagination offset

        Returns:
            List of templates (without nested tasks, for performance)
        """
        return self.template_repo.list_templates(
            status=status,
            limit=limit,
            offset=offset,
        )
