"""Assignment validation logic"""

from typing import TYPE_CHECKING
import logging
import re

from workflow.exceptions import ValidationError

if TYPE_CHECKING:
    from workflow.models.template import Phase

logger = logging.getLogger(__name__)


class AssignmentValidator:
    """Validate specialist assignments and agent properties"""

    @staticmethod
    def validate_all_phases_assigned(
        phases: list['Phase'],
        assignments: dict[str, str | int],
    ) -> None:
        """
        Validate all phases have assignment.

        Args:
            phases: List of Phase objects from template
            assignments: {phase_key → email | agent_id}

        Raises:
            ValidationError: If missing phase or invalid format
        """
        phase_keys = {phase.phase_key for phase in phases}
        assignment_keys = set(assignments.keys())

        # Check all phases have assignments
        missing = phase_keys - assignment_keys
        if missing:
            raise ValidationError(
                f"Missing assignments for phases: {missing}",
                details={
                    'missing_phases': list(missing),
                    'required_phases': list(phase_keys),
                },
            )

        # Check no extra phases in assignments
        extra = assignment_keys - phase_keys
        if extra:
            logger.warning(
                f"Extra phases in assignments (ignored): {extra}"
            )

        # Validate assignment values
        for phase_key, identifier in assignments.items():
            if isinstance(identifier, str):
                if not identifier or len(identifier) > 255:
                    raise ValidationError(
                        f"Invalid identifier for phase '{phase_key}': {identifier}",
                        details={'phase_key': phase_key},
                    )
            elif isinstance(identifier, int):
                if identifier < 1:
                    raise ValidationError(
                        f"Invalid agent_id for phase '{phase_key}': {identifier}",
                        details={'phase_key': phase_key},
                    )
            else:
                raise ValidationError(
                    f"Invalid assignment type for phase '{phase_key}': {type(identifier)}",
                    details={'phase_key': phase_key},
                )

    @staticmethod
    def validate_agent(
        name: str,
        email: str,
        specialist_type: str,
    ) -> None:
        """
        Validate agent properties.

        Args:
            name: Display name
            email: Email address
            specialist_type: Agent type (pm, engineer, qa, devops)

        Raises:
            ValidationError: If any property invalid
        """
        # Validate name
        if not name or len(name) > 255:
            raise ValidationError(
                f"Invalid agent name: '{name}'",
                details={'name': name},
            )

        # Validate email
        email_pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
        if not email or not re.match(email_pattern, email):
            raise ValidationError(
                f"Invalid email address: '{email}'",
                details={'email': email},
            )

        if len(email) > 255:
            raise ValidationError(
                f"Email address too long: {len(email)} chars (max 255)",
                details={'email': email},
            )

        # Validate specialist_type
        valid_types = {'pm', 'engineer', 'qa', 'devops'}
        if specialist_type not in valid_types:
            raise ValidationError(
                f"Invalid specialist_type: '{specialist_type}'",
                details={
                    'specialist_type': specialist_type,
                    'valid_types': list(valid_types),
                },
            )

    @staticmethod
    def validate_specialist_type_match(
        specialist_type: str,
        required_type: str,
    ) -> bool:
        """
        Check if specialist type matches requirement.

        Note: Returns False for mismatch (warning level),
        not raising error. Caller decides if strict.

        Args:
            specialist_type: Actual specialist type
            required_type: Required phase specialist type

        Returns:
            True if match, False if mismatch
        """
        return specialist_type == required_type
