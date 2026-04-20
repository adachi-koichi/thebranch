"""Unit tests for workflow validators"""

import pytest
from workflow.exceptions import ValidationError, CircularDependencyError
from workflow.models import Phase, TaskDef


class TestTemplateValidator:
    """TemplateValidator unit tests"""

    def test_validate_phase_valid(self, template_validator, template_repo_mock):
        """Valid phase should not raise"""
        template_repo_mock.get_phases.return_value = []
        # Should not raise
        template_validator.validate_phase(
            template_id=1,
            phase_key="planning",
            specialist_type="pm",
            phase_order=1,
        )

    def test_validate_phase_invalid_specialist_type(self, template_validator):
        """Invalid specialist_type should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_phase(
                template_id=1,
                phase_key="phase1",
                specialist_type="invalid_type",
                phase_order=1,
            )
        assert "Invalid specialist_type" in str(exc_info.value)

    def test_validate_task_def_valid(self, template_validator, template_repo_mock):
        """Valid task def should not raise"""
        template_repo_mock.get_tasks_for_phase.return_value = []
        # Should not raise
        template_validator.validate_task_def(
            phase_id=1,
            task_key="task1",
            depends_on_key=None,
        )

    def test_validate_template_complete_circular_dependency(
        self, template_validator, template_repo_mock
    ):
        """Circular dependency should raise CircularDependencyError"""
        phase = Phase(
            id=1,
            template_id=1,
            phase_key="phase1",
            phase_label="Phase 1",
            specialist_type="engineer",
            phase_order=1,
        )
        task1 = TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key="task1",
            task_title="Task 1",
            depends_on_key="task2",
        )
        task2 = TaskDef(
            id=2,
            phase_id=1,
            template_id=1,
            task_key="task2",
            task_title="Task 2",
            depends_on_key="task1",
        )
        template_repo_mock.get_phases.return_value = [phase]
        template_repo_mock.get_tasks_for_phase.return_value = [task1, task2]

        with pytest.raises(CircularDependencyError):
            template_validator.validate_template_complete(template_id=1)


class TestInstanceValidator:
    """InstanceValidator unit tests"""

    def test_validate_instance_exists_found(self, instance_validator, instance_repo_mock):
        """Validate instance exists - found"""
        from workflow.models.instance import WorkflowInstance
        instance = WorkflowInstance(id=1, template_id=1, name="Test", status="ready")
        instance_repo_mock.get_instance.return_value = instance
        # Should not raise
        instance_validator.validate_instance_exists(instance_id=1)

    def test_validate_instance_exists_not_found(self, instance_validator, instance_repo_mock):
        """Validate instance exists - not found"""
        from workflow.exceptions import InstanceNotFoundError
        instance_repo_mock.get_instance.return_value = None
        with pytest.raises(InstanceNotFoundError):
            instance_validator.validate_instance_exists(instance_id=999)

    def test_validate_template_published(self, instance_validator, template_repo_mock):
        """Validate template is published"""
        from workflow.models import Template
        template = Template(id=1, name="Test", status="published")
        template_repo_mock.get_template.return_value = template
        # Should not raise
        instance_validator.validate_template_published(template_id=1)

    def test_validate_template_not_published(self, instance_validator, template_repo_mock):
        """Validate template is not published raises error"""
        from workflow.models import Template
        template = Template(id=1, name="Test", status="draft")
        template_repo_mock.get_template.return_value = template
        with pytest.raises(ValidationError):
            instance_validator.validate_template_published(template_id=1)


class TestTaskValidator:
    """TaskValidator unit tests"""

    def test_validate_no_cycles_valid(self, task_validator, task_repo_mock):
        """Validate no cycles in DAG - valid"""
        task_repo_mock.get_instance_tasks.return_value = []
        # Should not raise
        task_validator.validate_no_cycles(instance_id=1)

    def test_validate_task_properties_valid(self, task_validator):
        """Validate task properties - valid"""
        # Should not raise
        task_validator.validate_task_properties(
            title="Test Task",
            assignee="test@example.com",
            phase="testing",
            priority=1,
        )

    def test_validate_task_properties_title_too_long(self, task_validator):
        """Validate task properties - title too long"""
        with pytest.raises(ValidationError):
            task_validator.validate_task_properties(
                title="x" * 1025,
                assignee="test@example.com",
                phase="testing",
                priority=1,
            )

    def test_validate_task_properties_invalid_priority(self, task_validator):
        """Validate task properties - invalid priority"""
        with pytest.raises(ValidationError):
            task_validator.validate_task_properties(
                title="Test Task",
                assignee="test@example.com",
                phase="testing",
                priority=10,
            )


class TestAssignmentValidator:
    """AssignmentValidator unit tests"""

    def test_validate_agent_valid(self):
        """Validate agent - valid"""
        from workflow.validation.assignment import AssignmentValidator
        # Should not raise
        AssignmentValidator.validate_agent(
            name="Alice Johnson",
            email="alice@example.com",
            specialist_type="pm",
        )

    def test_validate_agent_invalid_email(self):
        """Validate agent - invalid email"""
        from workflow.validation.assignment import AssignmentValidator
        with pytest.raises(ValidationError):
            AssignmentValidator.validate_agent(
                name="Alice",
                email="invalid-email",
                specialist_type="pm",
            )

    def test_validate_specialist_type_match_valid(self):
        """Validate specialist type match - valid"""
        from workflow.validation.assignment import AssignmentValidator
        result = AssignmentValidator.validate_specialist_type_match("pm", "pm")
        assert result is True

    def test_validate_specialist_type_match_invalid(self):
        """Validate specialist type match - invalid"""
        from workflow.validation.assignment import AssignmentValidator
        result = AssignmentValidator.validate_specialist_type_match("pm", "engineer")
        assert result is False
