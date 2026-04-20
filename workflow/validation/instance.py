"""Instance validation logic"""

from typing import TYPE_CHECKING
import logging

from workflow.exceptions import ValidationError, InstanceNotFoundError

if TYPE_CHECKING:
    from workflow.repositories.instance import InstanceRepository
    from workflow.repositories.template import TemplateRepository
    from workflow.models.instance import WorkflowInstance

logger = logging.getLogger(__name__)


class InstanceValidator:
    """Validate workflow instance structure and state"""

    def __init__(
        self,
        instance_repo: 'InstanceRepository',
        template_repo: 'TemplateRepository',
    ) -> None:
        self.instance_repo = instance_repo
        self.template_repo = template_repo

    def validate_instance_exists(self, instance_id: int) -> None:
        """
        Check instance exists.

        Raises:
            InstanceNotFoundError: If instance not found
        """
        instance = self.instance_repo.get_instance(instance_id)
        if not instance:
            raise InstanceNotFoundError(f"Instance {instance_id} not found")

    def validate_instance_status(
        self,
        instance: 'WorkflowInstance',
        expected_status: str,
    ) -> None:
        """
        Validate instance has expected status.

        Args:
            instance: WorkflowInstance object
            expected_status: Expected status value

        Raises:
            ValidationError: If status mismatch
        """
        if instance.status != expected_status:
            raise ValidationError(
                f"Instance status is '{instance.status}', expected '{expected_status}'",
                details={
                    'instance_id': instance.id,
                    'current_status': instance.status,
                    'expected_status': expected_status,
                },
            )

    def validate_template_published(self, template_id: int) -> None:
        """
        Check template is in published status.

        Raises:
            ValidationError: If template not published
        """
        template = self.template_repo.get_template(template_id)
        if not template:
            raise ValidationError(
                f"Template {template_id} not found",
                details={'template_id': template_id},
            )

        if template.status != 'published':
            raise ValidationError(
                f"Template {template_id} is not published (status={template.status})",
                details={
                    'template_id': template_id,
                    'status': template.status,
                },
            )

    def validate_phase_instance_status(
        self,
        instance_id: int,
        phase_key: str,
        expected_statuses: list[str],
    ) -> None:
        """
        Validate phase instance is in one of expected statuses.

        Args:
            instance_id: Workflow instance id
            phase_key: Phase key
            expected_statuses: List of allowed statuses

        Raises:
            ValidationError: If phase status not in expected list
        """
        phase_instance = self.instance_repo.get_phase_instance(
            instance_id, phase_key
        )

        if not phase_instance:
            raise ValidationError(
                f"Phase '{phase_key}' not found in instance {instance_id}",
                details={
                    'instance_id': instance_id,
                    'phase_key': phase_key,
                },
            )

        if phase_instance.status not in expected_statuses:
            raise ValidationError(
                f"Phase '{phase_key}' status is '{phase_instance.status}', "
                f"expected one of: {expected_statuses}",
                details={
                    'instance_id': instance_id,
                    'phase_key': phase_key,
                    'current_status': phase_instance.status,
                    'expected_statuses': expected_statuses,
                },
            )
