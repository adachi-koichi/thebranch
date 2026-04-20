"""Tests for workflow validation module"""

import pytest
from unittest.mock import MagicMock

from workflow.exceptions import (
    ValidationError,
    CircularDependencyError,
    InstanceNotFoundError,
)
from workflow.models import Phase, TaskDef, Template
from workflow.models.instance import WorkflowInstance, PhaseInstance
from workflow.models.task import TaskDependency
from workflow.validation.template import TemplateValidator
from workflow.validation.instance import InstanceValidator
from workflow.validation.task import TaskValidator


class TestTemplateValidator:
    """Tests for TemplateValidator"""

    def test_validate_phase_valid(self, template_validator, mock_template_repo):
        """Valid phase should not raise"""
        mock_template_repo.get_phases.return_value = []
        template_validator.validate_phase(
            template_id=1,
            phase_key='phase1',
            specialist_type='engineer',
            phase_order=1,
        )

    def test_validate_phase_invalid_specialist_type(self, template_validator):
        """Invalid specialist_type should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_phase(
                template_id=1,
                phase_key='phase1',
                specialist_type='invalid_type',
                phase_order=1,
            )
        assert 'Invalid specialist_type' in str(exc_info.value)

    def test_validate_phase_key_duplicate(self, template_validator, mock_template_repo):
        """Duplicate phase_key should raise ValidationError"""
        existing_phase = Phase(
            id=1,
            template_id=1,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='engineer',
            phase_order=1,
        )
        mock_template_repo.get_phases.return_value = [existing_phase]

        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_phase(
                template_id=1,
                phase_key='phase1',
                specialist_type='qa',
                phase_order=2,
            )
        assert 'already exists' in str(exc_info.value)

    def test_validate_phase_order_invalid(self, template_validator, mock_template_repo):
        """Invalid phase_order should raise ValidationError"""
        mock_template_repo.get_phases.return_value = []

        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_phase(
                template_id=1,
                phase_key='phase1',
                specialist_type='engineer',
                phase_order=0,
            )
        assert 'phase_order must be >= 1' in str(exc_info.value)

    def test_validate_task_def_valid(self, template_validator, mock_template_repo):
        """Valid task_def should not raise"""
        mock_template_repo.get_tasks_for_phase.return_value = []

        template_validator.validate_task_def(
            phase_id=1,
            task_key='task1',
            depends_on_key=None,
        )

    def test_validate_task_def_duplicate_key(self, template_validator, mock_template_repo):
        """Duplicate task_key should raise ValidationError"""
        existing_task = TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key='task1',
            task_title='Task 1',
        )
        mock_template_repo.get_tasks_for_phase.return_value = [existing_task]

        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_task_def(
                phase_id=1,
                task_key='task1',
                depends_on_key=None,
            )
        assert 'already exists' in str(exc_info.value)

    def test_validate_task_def_invalid_dependency(
        self, template_validator, mock_template_repo
    ):
        """Invalid depends_on_key should raise ValidationError"""
        existing_task = TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key='task1',
            task_title='Task 1',
        )
        mock_template_repo.get_tasks_for_phase.return_value = [existing_task]

        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_task_def(
                phase_id=1,
                task_key='task2',
                depends_on_key='task_nonexistent',
            )
        assert 'not found' in str(exc_info.value)

    def test_validate_template_complete_valid(self, template_validator, mock_template_repo):
        """Valid template with phases and tasks should not raise"""
        phase = Phase(
            id=1,
            template_id=1,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='engineer',
            phase_order=1,
        )
        task = TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key='task1',
            task_title='Task 1',
            depends_on_key=None,
        )
        mock_template_repo.get_phases.return_value = [phase]
        mock_template_repo.get_tasks_for_phase.return_value = [task]

        # Should not raise
        template_validator.validate_template_complete(template_id=1)

    def test_validate_template_complete_no_phases(
        self, template_validator, mock_template_repo
    ):
        """Template with no phases should raise ValidationError"""
        mock_template_repo.get_phases.return_value = []

        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_template_complete(template_id=1)
        assert 'no phases' in str(exc_info.value)

    def test_validate_template_complete_empty_phase(
        self, template_validator, mock_template_repo
    ):
        """Phase with no tasks should raise ValidationError"""
        phase = Phase(
            id=1,
            template_id=1,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='engineer',
            phase_order=1,
        )
        mock_template_repo.get_phases.return_value = [phase]
        mock_template_repo.get_tasks_for_phase.return_value = []

        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_template_complete(template_id=1)
        assert 'no tasks' in str(exc_info.value)

    def test_validate_template_complete_circular_dependency(
        self, template_validator, mock_template_repo
    ):
        """Circular dependency should raise CircularDependencyError"""
        phase = Phase(
            id=1,
            template_id=1,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='engineer',
            phase_order=1,
        )
        task1 = TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key='task1',
            task_title='Task 1',
            depends_on_key='task2',
        )
        task2 = TaskDef(
            id=2,
            phase_id=1,
            template_id=1,
            task_key='task2',
            task_title='Task 2',
            depends_on_key='task1',
        )
        mock_template_repo.get_phases.return_value = [phase]
        mock_template_repo.get_tasks_for_phase.return_value = [task1, task2]

        with pytest.raises(CircularDependencyError):
            template_validator.validate_template_complete(template_id=1)


class TestInstanceValidator:
    """Tests for InstanceValidator"""

    def test_validate_instance_exists(self, instance_validator, mock_instance_repo):
        """Existing instance should not raise"""
        instance = WorkflowInstance(
            id=1,
            template_id=1,
            name='Test',
            status='active',
        )
        mock_instance_repo.get_instance.return_value = instance

        instance_validator.validate_instance_exists(instance_id=1)

    def test_validate_instance_not_exists(self, instance_validator, mock_instance_repo):
        """Non-existent instance should raise InstanceNotFoundError"""
        mock_instance_repo.get_instance.return_value = None

        with pytest.raises(InstanceNotFoundError):
            instance_validator.validate_instance_exists(instance_id=1)

    def test_validate_instance_status_valid(
        self, instance_validator, sample_workflow_instance
    ):
        """Instance with matching status should not raise"""
        instance_validator.validate_instance_status(
            instance=sample_workflow_instance,
            expected_status='active',
        )

    def test_validate_instance_status_mismatch(
        self, instance_validator, sample_workflow_instance
    ):
        """Instance with mismatched status should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            instance_validator.validate_instance_status(
                instance=sample_workflow_instance,
                expected_status='completed',
            )
        assert 'status is' in str(exc_info.value)

    def test_validate_template_published(self, instance_validator, mock_template_repo):
        """Published template should not raise"""
        template = Template(
            id=1,
            name='Test',
            status='published',
        )
        mock_template_repo.get_template.return_value = template

        instance_validator.validate_template_published(template_id=1)

    def test_validate_template_not_published(self, instance_validator, mock_template_repo):
        """Non-published template should raise ValidationError"""
        template = Template(
            id=1,
            name='Test',
            status='draft',
        )
        mock_template_repo.get_template.return_value = template

        with pytest.raises(ValidationError) as exc_info:
            instance_validator.validate_template_published(template_id=1)
        assert 'not published' in str(exc_info.value)

    def test_validate_template_not_found(self, instance_validator, mock_template_repo):
        """Non-existent template should raise ValidationError"""
        mock_template_repo.get_template.return_value = None

        with pytest.raises(ValidationError) as exc_info:
            instance_validator.validate_template_published(template_id=1)
        assert 'not found' in str(exc_info.value)

    def test_validate_phase_instance_status_valid(
        self, instance_validator, mock_instance_repo
    ):
        """Phase instance with valid status should not raise"""
        phase_instance = PhaseInstance(
            id=1,
            instance_id=1,
            phase_key='phase1',
            status='in_progress',
        )
        mock_instance_repo.get_phase_instance.return_value = phase_instance

        instance_validator.validate_phase_instance_status(
            instance_id=1,
            phase_key='phase1',
            expected_statuses=['pending', 'in_progress'],
        )

    def test_validate_phase_instance_status_mismatch(
        self, instance_validator, mock_instance_repo
    ):
        """Phase instance with mismatched status should raise ValidationError"""
        phase_instance = PhaseInstance(
            id=1,
            instance_id=1,
            phase_key='phase1',
            status='completed',
        )
        mock_instance_repo.get_phase_instance.return_value = phase_instance

        with pytest.raises(ValidationError) as exc_info:
            instance_validator.validate_phase_instance_status(
                instance_id=1,
                phase_key='phase1',
                expected_statuses=['pending', 'in_progress'],
            )
        assert 'status is' in str(exc_info.value)

    def test_validate_phase_instance_not_found(
        self, instance_validator, mock_instance_repo
    ):
        """Non-existent phase instance should raise ValidationError"""
        mock_instance_repo.get_phase_instance.return_value = None

        with pytest.raises(ValidationError) as exc_info:
            instance_validator.validate_phase_instance_status(
                instance_id=1,
                phase_key='phase1',
                expected_statuses=['pending'],
            )
        assert 'not found' in str(exc_info.value)


class TestTaskValidator:
    """Tests for TaskValidator"""

    def test_validate_no_cycles_no_tasks(self, task_validator, mock_task_repo):
        """Instance with no tasks should not raise"""
        mock_task_repo.get_instance_tasks.return_value = []

        # Should not raise
        task_validator.validate_no_cycles(instance_id=1)

    def test_validate_no_cycles_valid_dag(self, task_validator, mock_task_repo):
        """Valid DAG should not raise"""
        task1 = MagicMock()
        task1.id = 1
        task2 = MagicMock()
        task2.id = 2
        task3 = MagicMock()
        task3.id = 3

        mock_task_repo.get_instance_tasks.return_value = [task1, task2, task3]

        dep1 = MagicMock()
        dep1.predecessor_id = 1
        dep1.successor_id = 2
        dep2 = MagicMock()
        dep2.predecessor_id = 2
        dep2.successor_id = 3

        mock_task_repo.get_task_dependencies.return_value = [dep1, dep2]

        # Should not raise
        task_validator.validate_no_cycles(instance_id=1)

    def test_validate_no_cycles_circular_dependency(self, task_validator, mock_task_repo):
        """Circular dependency should raise CircularDependencyError"""
        task1 = MagicMock()
        task1.id = 1
        task2 = MagicMock()
        task2.id = 2

        mock_task_repo.get_instance_tasks.return_value = [task1, task2]

        dep1 = MagicMock()
        dep1.predecessor_id = 1
        dep1.successor_id = 2
        dep2 = MagicMock()
        dep2.predecessor_id = 2
        dep2.successor_id = 1

        mock_task_repo.get_task_dependencies.return_value = [dep1, dep2]

        with pytest.raises(CircularDependencyError):
            task_validator.validate_no_cycles(instance_id=1)

    def test_validate_task_dependency_reference_valid(
        self, task_validator, mock_task_repo
    ):
        """Valid task references should not raise"""
        task1 = MagicMock()
        task1.id = 1
        task2 = MagicMock()
        task2.id = 2

        mock_task_repo.get_instance_tasks.return_value = [task1, task2]

        task_validator.validate_task_dependency_reference(
            instance_id=1,
            predecessor_id=1,
            successor_id=2,
        )

    def test_validate_task_dependency_reference_invalid_predecessor(
        self, task_validator, mock_task_repo
    ):
        """Non-existent predecessor should raise ValidationError"""
        task1 = MagicMock()
        task1.id = 1

        mock_task_repo.get_instance_tasks.return_value = [task1]

        with pytest.raises(ValidationError) as exc_info:
            task_validator.validate_task_dependency_reference(
                instance_id=1,
                predecessor_id=999,
                successor_id=1,
            )
        assert 'Predecessor task' in str(exc_info.value)

    def test_validate_task_dependency_reference_invalid_successor(
        self, task_validator, mock_task_repo
    ):
        """Non-existent successor should raise ValidationError"""
        task1 = MagicMock()
        task1.id = 1

        mock_task_repo.get_instance_tasks.return_value = [task1]

        with pytest.raises(ValidationError) as exc_info:
            task_validator.validate_task_dependency_reference(
                instance_id=1,
                predecessor_id=1,
                successor_id=999,
            )
        assert 'Successor task' in str(exc_info.value)

    def test_validate_task_properties_valid(self, task_validator):
        """Valid task properties should not raise"""
        task_validator.validate_task_properties(
            title='Valid Task Title',
            assignee='engineer@example.com',
            phase='phase1',
            priority=2,
        )

    def test_validate_task_properties_invalid_title_empty(self, task_validator):
        """Empty title should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            task_validator.validate_task_properties(
                title='',
                assignee='engineer@example.com',
                phase='phase1',
                priority=2,
            )
        assert 'Invalid task title' in str(exc_info.value)

    def test_validate_task_properties_invalid_title_too_long(self, task_validator):
        """Title exceeding 1024 chars should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            task_validator.validate_task_properties(
                title='a' * 1025,
                assignee='engineer@example.com',
                phase='phase1',
                priority=2,
            )
        assert 'Invalid task title' in str(exc_info.value)

    def test_validate_task_properties_invalid_email(self, task_validator):
        """Invalid email should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            task_validator.validate_task_properties(
                title='Valid Title',
                assignee='invalid_email',
                phase='phase1',
                priority=2,
            )
        assert 'Invalid assignee email' in str(exc_info.value)

    def test_validate_task_properties_email_too_long(self, task_validator):
        """Email exceeding 255 chars should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            task_validator.validate_task_properties(
                title='Valid Title',
                assignee='a' * 244 + '@example.com',  # 244 + 12 = 256 > 255
                phase='phase1',
                priority=2,
            )
        assert 'email too long' in str(exc_info.value)

    def test_validate_task_properties_invalid_phase(self, task_validator):
        """Empty phase should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            task_validator.validate_task_properties(
                title='Valid Title',
                assignee='engineer@example.com',
                phase='',
                priority=2,
            )
        assert 'Invalid phase' in str(exc_info.value)

    def test_validate_task_properties_invalid_priority_low(self, task_validator):
        """Priority < 1 should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            task_validator.validate_task_properties(
                title='Valid Title',
                assignee='engineer@example.com',
                phase='phase1',
                priority=0,
            )
        assert 'Invalid priority' in str(exc_info.value)

    def test_validate_task_properties_invalid_priority_high(self, task_validator):
        """Priority > 5 should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            task_validator.validate_task_properties(
                title='Valid Title',
                assignee='engineer@example.com',
                phase='phase1',
                priority=6,
            )
        assert 'Invalid priority' in str(exc_info.value)

    def test_validate_task_properties_valid_priority_range(self, task_validator):
        """Priority 1-5 should not raise"""
        for priority in range(1, 6):
            task_validator.validate_task_properties(
                title='Valid Title',
                assignee='engineer@example.com',
                phase='phase1',
                priority=priority,
            )
