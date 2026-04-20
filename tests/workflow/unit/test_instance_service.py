"""Unit tests for WorkflowInstanceService"""

import pytest
from workflow.models.instance import WorkflowInstance
from workflow.exceptions import (
    TemplateNotFoundError,
    ValidationError,
    SpecialistNotFoundError,
    InstanceNotFoundError,
)
from workflow.services.instance import WorkflowInstanceService


class TestWorkflowInstanceService:
    """WorkflowInstanceService unit tests"""

    def test_instantiate_workflow_valid(
        self, instance_service, instance_repo_mock, template_repo_mock,
        sample_template, sample_phases, sample_agents
    ):
        """Instantiate workflow with valid inputs"""
        sample_template.status = "published"
        template_repo_mock.get_template.return_value = sample_template
        template_repo_mock.get_phases.return_value = sample_phases[:2]

        expected_instance = WorkflowInstance(
            id=1, template_id=1, name="Product Launch #1", status="ready"
        )
        instance_repo_mock.create_instance.return_value = expected_instance
        instance_repo_mock.update_instance.return_value = expected_instance

        def resolve_assignments(template_id, assignments):
            return {
                phase_key: (sample_agents["alice"] if phase_key == "planning" else sample_agents["bob"])
                for phase_key in assignments.keys()
            }

        instance_service.assignment_svc.validate_and_resolve_assignments = resolve_assignments
        instance_service.task_gen_service.generate_tasks_for_instance = lambda instance_id, template_id: 0

        result = instance_service.instantiate_workflow(
            template_id=1,
            instance_name="Product Launch #1",
            specialist_assignments={
                "planning": "alice@example.com",
                "development": "bob@example.com",
            },
        )

        assert result.id == 1
        instance_repo_mock.create_instance.assert_called_once()

    def test_instantiate_workflow_template_not_found(
        self, instance_service, template_repo_mock
    ):
        """Instantiate with non-existent template raises TemplateNotFoundError"""
        template_repo_mock.get_template.return_value = None

        with pytest.raises(TemplateNotFoundError):
            instance_service.instantiate_workflow(
                template_id=999,
                instance_name="Test",
                specialist_assignments={},
            )

    def test_instantiate_workflow_unpublished_template(
        self, instance_service, template_repo_mock, sample_template
    ):
        """Instantiate with unpublished template raises ValidationError"""
        sample_template.status = "draft"
        template_repo_mock.get_template.return_value = sample_template

        with pytest.raises(ValidationError):
            instance_service.instantiate_workflow(
                template_id=1,
                instance_name="Test",
                specialist_assignments={},
            )

    def test_instantiate_workflow_missing_specialist(
        self, instance_service, template_repo_mock, sample_template, sample_phases
    ):
        """Instantiate with missing specialist raises SpecialistNotFoundError"""
        sample_template.status = "published"
        template_repo_mock.get_template.return_value = sample_template
        template_repo_mock.get_phases.return_value = sample_phases[:1]

        instance_service.assignment_svc.validate_and_resolve_assignments = (
            lambda template_id, assignments: (_ for _ in ()).throw(
                SpecialistNotFoundError("Specialist not found")
            )
        )

        with pytest.raises(SpecialistNotFoundError):
            instance_service.instantiate_workflow(
                template_id=1,
                instance_name="Test",
                specialist_assignments={},  # Missing specialist assignment
            )

    def test_get_instance_status(
        self, instance_service, instance_repo_mock, sample_workflow_instance
    ):
        """Get instance status"""
        instance_repo_mock.get_instance.return_value = sample_workflow_instance
        instance_repo_mock.get_instance_tasks.return_value = []
        instance_repo_mock.get_phase_instances.return_value = []

        result = instance_service.get_instance_status(instance_id=1)

        assert isinstance(result, dict)
        assert result["instance"].status == "ready"
        assert result["progress"]["total"] == 0
        instance_repo_mock.get_instance.assert_called_once_with(1)

    def test_get_instance_not_found(
        self, instance_service, instance_repo_mock
    ):
        """Get non-existent instance raises error"""
        instance_repo_mock.get_instance.return_value = None

        with pytest.raises(InstanceNotFoundError):
            instance_service.get_instance_status(instance_id=999)
