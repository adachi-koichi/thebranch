"""Tests for workflow services layer"""

import pytest
from unittest.mock import MagicMock

from workflow.exceptions import ValidationError, TemplateNotFoundError, SpecialistNotFoundError
from workflow.models import Template, Phase, TaskDef, Agent
from workflow.models.instance import WorkflowInstance
from workflow.services.template import TemplateService
from workflow.services.instance import WorkflowInstanceService
from workflow.services.task_gen import TaskGenerationService
from workflow.services.assignment import SpecialistAssignmentService


class TestTemplateService:
    """Tests for TemplateService (8 tests)"""

    def test_create_template_valid(self, template_service, mock_template_repo):
        """Valid template creation"""
        t = Template(id=1, name='Test', status='draft')
        mock_template_repo.create_template.return_value = t
        r = template_service.create_template(name='Test', description='Desc', created_by='u@e.com')
        assert r.id == 1

    def test_create_template_empty_name(self, template_service):
        """Empty name raises ValidationError"""
        with pytest.raises(ValidationError):
            template_service.create_template(name='', description='Desc')

    def test_create_template_long_name(self, template_service):
        """Long name raises ValidationError"""
        with pytest.raises(ValidationError):
            template_service.create_template(name='a' * 256, description='Desc')

    def test_add_phase_valid(self, template_service, mock_template_repo):
        """Valid phase addition"""
        p = Phase(id=1, template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='engineer', phase_order=1)
        mock_template_repo.get_template.return_value = Template(id=1, name='Test', status='draft')
        mock_template_repo.create_phase.return_value = p
        r = template_service.add_phase(template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='engineer', phase_order=1)
        assert r.phase_key == 'p1'

    def test_add_phase_invalid_specialist(self, template_service):
        """Invalid specialist raises ValidationError"""
        with pytest.raises(ValidationError):
            template_service.add_phase(template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='invalid', phase_order=1)

    def test_publish_template_valid(self, template_service, mock_template_repo):
        """Valid template publish"""
        t = Template(id=1, name='Test', status='draft')
        mock_template_repo.get_template.return_value = t
        mock_template_repo.get_phases.return_value = [Phase(id=1, template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='engineer', phase_order=1)]
        mock_template_repo.get_tasks_for_phase.return_value = [TaskDef(id=1, phase_id=1, template_id=1, task_key='t1', task_title='Task 1')]
        r = template_service.publish_template(template_id=1)
        assert r.status == 'published'

    def test_get_template(self, template_service, mock_template_repo):
        """get_template returns template"""
        t = Template(id=1, name='Test', status='draft')
        mock_template_repo.get_template_with_phases_and_tasks.return_value = t
        r = template_service.get_template(template_id=1)
        assert r.id == 1

    def test_list_templates(self, template_service, mock_template_repo):
        """list_templates returns templates"""
        mock_template_repo.list_templates.return_value = [Template(id=1, name='T1', status='draft')]
        r = template_service.list_templates()
        assert len(r) == 1


class TestWorkflowInstanceService:
    """Tests for WorkflowInstanceService (7 tests)"""

    def test_instantiate_workflow_published(self, instance_service, mock_instance_repo, mock_template_repo):
        """instantiate_workflow with published template"""
        from unittest.mock import patch
        i = WorkflowInstance(id=1, template_id=1, name='Test', status='pending')
        mock_template_repo.get_template.return_value = Template(id=1, name='Test', status='published')
        mock_instance_repo.create_instance.return_value = i
        mock_template_repo.get_phases.return_value = []
        mock_instance_repo.assign_specialist.return_value = None
        mock_instance_repo.create_phase_instance.return_value = None
        mock_instance_repo.update_instance.return_value = None
        with patch.object(instance_service.task_gen_service, 'generate_tasks_for_instance', return_value=0):
            r = instance_service.instantiate_workflow(template_id=1, instance_name='Test', specialist_assignments={})
        assert r.id == 1

    def test_instantiate_workflow_not_published(self, instance_service, mock_template_repo):
        """instantiate_workflow with non-published template fails"""
        mock_template_repo.get_template.return_value = Template(id=1, name='Test', status='draft')
        with pytest.raises(ValidationError):
            instance_service.instantiate_workflow(template_id=1, instance_name='Test', specialist_assignments={})

    def test_instantiate_workflow_template_not_found(self, instance_service, mock_template_repo):
        """instantiate_workflow with non-existent template fails"""
        mock_template_repo.get_template.return_value = None
        with pytest.raises(TemplateNotFoundError):
            instance_service.instantiate_workflow(template_id=999, instance_name='Test', specialist_assignments={})

    def test_get_instance_status(self, instance_service, mock_instance_repo):
        """get_instance_status returns dict with progress"""
        i = WorkflowInstance(id=1, template_id=1, name='Test', status='active')
        mock_instance_repo.get_instance.return_value = i
        mock_instance_repo.get_phase_instances.return_value = []
        mock_instance_repo.get_instance_tasks.return_value = []
        r = instance_service.get_instance_status(instance_id=1)
        assert r['instance'].id == 1
        assert r['progress']['total'] == 0

    def test_get_instance(self, instance_service, mock_instance_repo):
        """get_instance returns instance"""
        i = WorkflowInstance(id=1, template_id=1, name='Test', status='pending')
        mock_instance_repo.get_instance.return_value = i
        r = instance_service.get_instance(instance_id=1)
        assert r.id == 1

    def test_list_instances(self, instance_service, mock_instance_repo):
        """list_instances returns instances"""
        mock_instance_repo.list_instances.return_value = [WorkflowInstance(id=1, template_id=1, name='T1', status='pending')]
        r = instance_service.list_instances()
        assert len(r) == 1

    def test_advance_phase(self, instance_service, mock_instance_repo, mock_template_repo):
        """advance_phase updates phase status"""
        i = WorkflowInstance(id=1, template_id=1, name='Test', status='active')
        from workflow.models.instance import PhaseInstance
        p = PhaseInstance(id=1, instance_id=1, phase_key='p1', status='waiting')
        phase = Phase(id=1, template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='engineer', phase_order=1)
        mock_instance_repo.get_instance.return_value = i
        mock_instance_repo.get_phase_instance.return_value = p
        mock_template_repo.get_phases.return_value = [phase]
        mock_instance_repo.update_phase_instance.return_value = None
        r = instance_service.advance_phase(instance_id=1, phase_key='p1')
        assert r.status == 'ready'


class TestTaskGenerationService:
    """Tests for TaskGenerationService (6 tests)"""

    def test_apply_placeholders(self, task_gen_service):
        """_apply_placeholders resolves placeholders"""
        r = task_gen_service._apply_placeholders('Task {{x}}', {'x': 'Y'})
        assert 'Y' in r

    def test_apply_placeholders_empty(self, task_gen_service):
        """_apply_placeholders handles empty context"""
        r = task_gen_service._apply_placeholders('Task', {})
        assert r == 'Task'

    def test_apply_placeholders_missing(self, task_gen_service):
        """_apply_placeholders handles missing placeholder"""
        r = task_gen_service._apply_placeholders('Task {{x}}', {})
        assert '{{x}}' in r

    def test_create_intra_phase_dependencies(self, task_gen_service, mock_task_repo):
        """_create_intra_phase_dependencies creates dependencies"""
        from workflow.models.task import DevTask
        t1 = TaskDef(id=1, phase_id=1, template_id=1, task_key='t1', task_title='Task 1', depends_on_key=None)
        t2 = TaskDef(id=2, phase_id=1, template_id=1, task_key='t2', task_title='Task 2', depends_on_key='t1')
        phase = Phase(id=1, template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='engineer', phase_order=1)
        d1 = DevTask(id=1, title='Task 1', phase='p1', workflow_instance_id=1, assignee='e@e.com')
        d2 = DevTask(id=2, title='Task 2', phase='p1', workflow_instance_id=1, assignee='e@e.com')
        mock_task_repo.create_task_dependency.return_value = None
        task_gen_service._create_intra_phase_dependencies(phase=phase, task_defs=[t1, t2], phase_tasks=[d1, d2])
        mock_task_repo.create_task_dependency.assert_called()

    def test_create_inter_phase_dependencies(self, task_gen_service, mock_task_repo):
        """_create_inter_phase_dependencies creates dependencies"""
        from workflow.models.task import DevTask
        p1 = Phase(id=1, template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='engineer', phase_order=1)
        p2 = Phase(id=2, template_id=1, phase_key='p2', phase_label='Phase 2', specialist_type='engineer', phase_order=2)
        d1 = DevTask(id=1, title='Task 1', phase='p1', workflow_instance_id=1, assignee='e@e.com')
        d2 = DevTask(id=2, title='Task 2', phase='p2', workflow_instance_id=1, assignee='e@e.com')
        mock_task_repo.create_task_dependency.return_value = None
        task_gen_service._create_inter_phase_dependencies(phases=[p1, p2], phase_task_map={'p1': [d1], 'p2': [d2]})
        mock_task_repo.create_task_dependency.assert_called()

    def test_create_task_from_def(self, task_gen_service, mock_task_repo):
        """_create_task_from_def creates task from definition"""
        from workflow.models import Agent
        from workflow.models.task import DevTask
        t = TaskDef(id=1, phase_id=1, template_id=1, task_key='t1', task_title='Task 1', task_description='Desc')
        agent = Agent(id=1, name='E', email='e@e.com', specialist_type='engineer')
        task = DevTask(id=1, title='Task 1', phase='p1', workflow_instance_id=1, assignee='e@e.com')
        mock_task_repo.create_task.return_value = task
        r = task_gen_service._create_task_from_def(
            instance_id=1,
            phase_key='p1',
            task_def=t,
            specialist=agent,
            phase_label='Phase 1',
            workflow_name='WF'
        )
        assert r.title == 'Task 1'


class TestSpecialistAssignmentService:
    """Tests for SpecialistAssignmentService (7 tests)"""

    def test_validate_and_resolve_assignments(self, assignment_service, mock_specialist_repo):
        """validate_and_resolve_assignments validates assignments"""
        a = Agent(id=1, email='e@e.com', specialist_type='engineer', name='E')
        p = Phase(id=1, template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='engineer', phase_order=1)
        mock_specialist_repo.get_template_phases.return_value = [p]
        mock_specialist_repo.get_specialist_by_email.return_value = a
        r = assignment_service.validate_and_resolve_assignments(template_id=1, assignments={'p1': 'e@e.com'})
        assert 'p1' in r

    def test_validate_and_resolve_assignments_missing_phase(self, assignment_service, mock_specialist_repo, assignment_validator):
        """validate_and_resolve_assignments fails on missing phase"""
        p = Phase(id=1, template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='engineer', phase_order=1)
        mock_specialist_repo.get_template_phases.return_value = [p]
        assignment_validator.validate_all_phases_assigned.side_effect = ValidationError("Missing phase")
        with pytest.raises(ValidationError):
            assignment_service.validate_and_resolve_assignments(template_id=1, assignments={})

    def test_validate_and_resolve_assignments_specialist_not_found(self, assignment_service, mock_specialist_repo, assignment_validator):
        """validate_and_resolve_assignments fails on missing specialist"""
        p = Phase(id=1, template_id=1, phase_key='p1', phase_label='Phase 1', specialist_type='engineer', phase_order=1)
        mock_specialist_repo.get_template_phases.return_value = [p]
        mock_specialist_repo.get_agent_by_email.return_value = None
        assignment_validator.validate_all_phases_assigned.return_value = None
        with pytest.raises(SpecialistNotFoundError):
            assignment_service.validate_and_resolve_assignments(template_id=1, assignments={'p1': 'x@e.com'})

    def test_create_specialist(self, assignment_service, mock_specialist_repo, assignment_validator):
        """create_specialist creates specialist"""
        a = Agent(id=1, email='n@e.com', specialist_type='engineer', name='N')
        mock_specialist_repo.get_agent_by_email.return_value = None
        mock_specialist_repo.create_agent.return_value = a
        assignment_validator.validate_agent.return_value = None
        r = assignment_service.create_specialist(name='N', email='n@e.com', specialist_type='engineer')
        assert r.email == 'n@e.com'

    def test_create_specialist_invalid_type(self, assignment_service):
        """create_specialist fails on invalid type"""
        with pytest.raises(ValidationError):
            assignment_service.create_specialist(email='n@e.com', specialist_type='invalid', name='N')

    def test_get_available_specialists(self, assignment_service, mock_specialist_repo):
        """get_available_specialists returns specialists"""
        a1 = Agent(id=1, email='e1@e.com', specialist_type='engineer', name='E1')
        a2 = Agent(id=2, email='e2@e.com', specialist_type='engineer', name='E2')
        mock_specialist_repo.get_agents.return_value = [a1, a2]
        r = assignment_service.get_available_specialists(specialist_type='engineer')
        assert len(r) == 2

    def test_get_available_specialists_empty(self, assignment_service, mock_specialist_repo):
        """get_available_specialists handles empty result"""
        mock_specialist_repo.get_agents.return_value = []
        r = assignment_service.get_available_specialists(specialist_type='engineer')
        assert len(r) == 0
