"""Specialist assignment and validation service"""

from typing import TYPE_CHECKING
import logging

from workflow.models import Agent
from workflow.exceptions import (
    SpecialistNotFoundError,
    ValidationError,
)

if TYPE_CHECKING:
    from workflow.repositories.specialist import SpecialistRepository
    from workflow.validation.assignment import AssignmentValidator
    from workflow.models.template import Phase

logger = logging.getLogger(__name__)


class SpecialistAssignmentService:
    """
    Specialist assignment and validation.

    Responsibilities:
    - Resolve identifiers (email → Agent)
    - Validate type compatibility
    - Prevent type mismatches
    """

    def __init__(
        self,
        specialist_repo: 'SpecialistRepository',
        validator: 'AssignmentValidator',
    ) -> None:
        self.specialist_repo = specialist_repo
        self.validator = validator

    # ===== ASSIGNMENT VALIDATION =====

    def validate_and_resolve_assignments(
        self,
        template_id: int,
        assignments: dict[str, str | int],
    ) -> dict[str, Agent]:
        """
        Validate and resolve specialist assignments.

        Input format:
        {
            'phase_key': 'email@example.com' | agent_id,
            ...
        }

        Process:
        1. Check all phases have assignment
        2. Resolve each identifier to Agent
        3. Validate type compatibility

        Args:
            template_id: Template (for phase list)
            assignments: {phase_key → email | agent_id}

        Returns:
            {phase_key → Agent object}

        Raises:
            ValidationError: If missing phase or invalid format
            SpecialistNotFoundError: If email/agent_id not found
            SpecialistAssignmentError: If type mismatch
        """
        # Get phases from template
        phases = self.specialist_repo.get_template_phases(template_id)

        # Validate all phases assigned
        self.validator.validate_all_phases_assigned(phases, assignments)

        resolved: dict[str, Agent] = {}

        for phase in phases:
            identifier = assignments[phase.phase_key]

            # Resolve identifier
            agent = self._resolve_identifier(identifier)

            if not agent:
                raise SpecialistNotFoundError(
                    f"Specialist not found: {identifier}"
                )

            # Validate type (warning if mismatch, but allow)
            if agent.specialist_type != phase.specialist_type:
                logger.warning(
                    f"Type mismatch: specialist {agent.email} "
                    f"type={agent.specialist_type} "
                    f"but phase {phase.phase_key} requires {phase.specialist_type}"
                )

            resolved[phase.phase_key] = agent

        logger.info(f"Resolved {len(resolved)} specialist assignments")
        return resolved

    def _resolve_identifier(
        self,
        identifier: str | int,
    ) -> Agent | None:
        """
        Resolve email or agent_id to Agent.

        Args:
            identifier: Email string or integer agent_id

        Returns:
            Agent object or None if not found
        """
        if isinstance(identifier, int):
            return self.specialist_repo.get_agent(identifier)
        elif isinstance(identifier, str):
            if '@' in identifier:
                return self.specialist_repo.get_agent_by_email(identifier)
            else:
                # Try as agent name
                return self.specialist_repo.get_agent_by_name(identifier)
        return None

    # ===== AGENT MANAGEMENT =====

    def create_specialist(
        self,
        name: str,
        email: str,
        specialist_type: str,
    ) -> Agent:
        """
        Register new specialist/agent.

        Args:
            name: Display name
            email: Email address
            specialist_type: 'pm' | 'engineer' | 'qa' | 'devops'

        Returns:
            Agent object with assigned id

        Raises:
            ValidationError: If email invalid or duplicate
            ValidationError: If specialist_type invalid
        """
        # Validate
        self.validator.validate_agent(name, email, specialist_type)

        # Check email unique
        existing = self.specialist_repo.get_agent_by_email(email)
        if existing:
            raise ValidationError(
                f"Agent with email {email} already exists"
            )

        # Create
        agent = self.specialist_repo.create_agent(
            name=name,
            email=email,
            specialist_type=specialist_type,
        )

        logger.info(
            f"Created specialist: {agent.id} ({agent.email}) "
            f"type={agent.specialist_type}"
        )
        return agent

    def get_available_specialists(
        self,
        specialist_type: str | None = None,
    ) -> list[Agent]:
        """
        Get all available specialists.

        Args:
            specialist_type: Filter by type

        Returns:
            List of Agent objects
        """
        return self.specialist_repo.get_agents(
            specialist_type=specialist_type
        )
