"""Unit tests for SpecialistAssignmentService"""

import pytest
from workflow.models import Agent
from workflow.exceptions import SpecialistNotFoundError, ValidationError
from workflow.services.assignment import SpecialistAssignmentService


class TestSpecialistAssignmentService:
    """SpecialistAssignmentService unit tests"""

    def test_validate_and_resolve_assignments_valid(
        self, assignment_service, specialist_repo_mock, assignment_validator_mock, sample_phases
    ):
        """Resolve valid specialist assignments"""
        specialist_repo_mock.get_template_phases.return_value = sample_phases[:2]
        alice = Agent(
            id=1, name="Alice", email="alice@example.com", specialist_type="pm"
        )
        bob = Agent(
            id=2, name="Bob", email="bob@example.com", specialist_type="engineer"
        )
        specialist_repo_mock.get_agent_by_email.side_effect = lambda email: (
            alice if email == "alice@example.com" else bob
        )

        assignments = {
            "planning": "alice@example.com",
            "development": "bob@example.com",
        }

        result = assignment_service.validate_and_resolve_assignments(
            template_id=1, assignments=assignments
        )

        assert result["planning"].email == "alice@example.com"
        assert result["development"].email == "bob@example.com"

    def test_validate_and_resolve_assignments_missing_phase(
        self, assignment_service, specialist_repo_mock, assignment_validator_mock, sample_phases
    ):
        """Missing phase assignment raises ValidationError"""
        specialist_repo_mock.get_template_phases.return_value = sample_phases
        assignment_validator_mock.validate_all_phases_assigned.side_effect = ValidationError(
            "Missing assignment for phase"
        )

        with pytest.raises(ValidationError):
            assignment_service.validate_and_resolve_assignments(
                template_id=1,
                assignments={"planning": "alice@example.com"},
            )

    def test_validate_and_resolve_assignments_specialist_not_found(
        self, assignment_service, specialist_repo_mock, sample_phases
    ):
        """Non-existent specialist raises SpecialistNotFoundError"""
        specialist_repo_mock.get_template_phases.return_value = sample_phases[:1]
        specialist_repo_mock.get_agent_by_email.return_value = None

        with pytest.raises(SpecialistNotFoundError):
            assignment_service.validate_and_resolve_assignments(
                template_id=1,
                assignments={"planning": "unknown@example.com"},
            )

    def test_validate_and_resolve_assignments_type_mismatch(
        self, assignment_service, specialist_repo_mock
    ):
        """Type mismatch logs warning but continues"""
        from workflow.models import Phase

        phase = Phase(
            id=1,
            template_id=1,
            phase_key="planning",
            phase_label="Planning",
            specialist_type="pm",
            phase_order=1,
        )
        specialist_repo_mock.get_template_phases.return_value = [phase]
        bob = Agent(
            id=2, name="Bob", email="bob@example.com", specialist_type="engineer"
        )
        specialist_repo_mock.get_agent_by_email.return_value = bob

        # Service logs warning but continues (returns assignment anyway)
        result = assignment_service.validate_and_resolve_assignments(
            template_id=1,
            assignments={"planning": "bob@example.com"},
        )

        assert result["planning"].email == "bob@example.com"
