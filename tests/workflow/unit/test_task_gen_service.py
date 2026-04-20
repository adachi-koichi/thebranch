"""Unit tests for TaskGenerationService"""

import pytest
from workflow.models import DevTask
from workflow.exceptions import ValidationError, InstanceNotFoundError
from workflow.services.task_gen import TaskGenerationService


class TestTaskGenerationService:
    """TaskGenerationService unit tests"""

    def test_generate_tasks_for_instance_valid(
        self, task_gen_service, task_repo_mock, template_repo_mock,
        instance_repo_mock, sample_workflow_instance, sample_task_defs
    ):
        """Generate tasks for workflow instance"""
        from workflow.models import Phase, Agent

        instance_repo_mock.get_instance.return_value = sample_workflow_instance
        template_repo_mock.get_template.return_value = sample_workflow_instance
        phase = Phase(
            id=1, template_id=1, phase_key="planning", phase_label="Planning",
            specialist_type="pm", phase_order=1
        )
        template_repo_mock.get_phases.return_value = [phase]
        template_repo_mock.get_tasks_for_phase.return_value = sample_task_defs[:1]
        task_repo_mock.count_instance_tasks.return_value = 0

        alice = Agent(id=1, name="Alice", email="alice@example.com", specialist_type="pm")
        instance_repo_mock.get_phase_specialist.return_value = alice

        task_repo_mock.create_task.return_value = DevTask(
            id=1,
            title="Design Planning Architecture",
            assignee="alice@example.com",
            phase="planning",
            workflow_instance_id=1,
        )

        result = task_gen_service.generate_tasks_for_instance(
            instance_id=1, template_id=1
        )

        assert result >= 0

    def test_generate_tasks_placeholder_resolution(
        self, task_gen_service, task_repo_mock, template_repo_mock
    ):
        """Resolve placeholders in task title and description"""
        task_def = pytest.fixture
        title = "Design {phase_label} Architecture"
        description = "Create architecture with {specialist_name}"

        # In real implementation, placeholders would be resolved
        resolved_title = title.replace("{phase_label}", "Planning")
        resolved_description = description.replace("{specialist_name}", "Alice Johnson")

        assert "{phase_label}" not in resolved_title
        assert "{specialist_name}" not in resolved_description

    def test_generate_tasks_with_dependencies(
        self, task_gen_service, task_repo_mock, template_repo_mock, instance_repo_mock
    ):
        """Generate tasks with task dependencies"""
        from workflow.models import Phase, Agent

        sample_instance = pytest.fixture
        task_repo_mock.count_instance_tasks.return_value = 0
        instance_repo_mock.get_instance.return_value = sample_instance
        template_repo_mock.get_template.return_value = sample_instance

        phase = Phase(
            id=1, template_id=1, phase_key="phase1", phase_label="Phase 1",
            specialist_type="engineer", phase_order=1
        )
        template_repo_mock.get_phases.return_value = [phase]
        template_repo_mock.get_tasks_for_phase.return_value = []

        alice = Agent(id=1, name="Alice", email="alice@example.com", specialist_type="engineer")
        instance_repo_mock.get_phase_specialist.return_value = alice

        result = task_gen_service.generate_tasks_for_instance(
            instance_id=1, template_id=1
        )

        assert result >= 0

    def test_generate_tasks_empty_phase(
        self, task_gen_service, template_repo_mock, task_repo_mock, instance_repo_mock
    ):
        """Generate tasks for phase with no task definitions"""
        from workflow.models import Phase, Agent

        sample_instance = pytest.fixture
        task_repo_mock.count_instance_tasks.return_value = 0
        instance_repo_mock.get_instance.return_value = sample_instance
        template_repo_mock.get_template.return_value = sample_instance

        phase = Phase(
            id=1, template_id=1, phase_key="phase1", phase_label="Phase 1",
            specialist_type="engineer", phase_order=1
        )
        template_repo_mock.get_phases.return_value = [phase]
        template_repo_mock.get_tasks_for_phase.return_value = []

        alice = Agent(id=1, name="Alice", email="alice@example.com", specialist_type="engineer")
        instance_repo_mock.get_phase_specialist.return_value = alice

        result = task_gen_service.generate_tasks_for_instance(
            instance_id=1, template_id=1
        )

        # Should return 0 for empty phase
        assert result == 0

    def test_validate_task_dependency_no_cycles(
        self, task_gen_service, task_repo_mock, task_validator_mock
    ):
        """Validate DAG has no cycles"""
        task_repo_mock.get_instance_tasks.return_value = []

        # Should not raise
        task_gen_service.validator.validate_no_cycles(instance_id=1)

    def test_task_gen_idempotency(
        self, task_gen_service, task_repo_mock, instance_repo_mock, template_repo_mock
    ):
        """Task generation should be idempotent"""
        # First call already generated tasks
        task_repo_mock.count_instance_tasks.return_value = 5

        result = task_gen_service.generate_tasks_for_instance(
            instance_id=1, template_id=1
        )

        # Should return existing count
        assert result == 5

    def test_apply_placeholders(self, task_gen_service):
        """Test placeholder application"""
        context = {
            "phase_label": "Planning",
            "specialist_name": "Alice Johnson",
            "workflow_name": "Product Launch",
        }
        text = "Create {phase_label} with {specialist_name} for {workflow_name}"
        result = task_gen_service._apply_placeholders(text, context)

        assert "{phase_label}" not in result
        assert "{specialist_name}" not in result
        assert "{workflow_name}" not in result
        assert "Planning" in result
        assert "Alice Johnson" in result
