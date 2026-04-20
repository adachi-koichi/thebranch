"""Workflow validation test fixtures"""

from unittest.mock import MagicMock
from datetime import datetime
import pytest

from workflow.models import Template, Phase, TaskDef
from workflow.models.instance import WorkflowInstance, PhaseInstance
from workflow.models.task import TaskDependency, DevTask
from workflow.validation.template import TemplateValidator
from workflow.validation.instance import InstanceValidator
from workflow.validation.task import TaskValidator
from workflow.validation.assignment import AssignmentValidator
from workflow.services.template import TemplateService
from workflow.services.instance import WorkflowInstanceService
from workflow.services.task_gen import TaskGenerationService
from workflow.services.assignment import SpecialistAssignmentService


@pytest.fixture
def mock_template_repo():
    """Mock TemplateRepository"""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_instance_repo():
    """Mock InstanceRepository"""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_task_repo():
    """Mock TaskRepository"""
    repo = MagicMock()
    return repo


@pytest.fixture
def template_validator(mock_template_repo):
    """TemplateValidator instance"""
    return TemplateValidator(mock_template_repo)


@pytest.fixture
def instance_validator(mock_instance_repo, mock_template_repo):
    """InstanceValidator instance"""
    return InstanceValidator(mock_instance_repo, mock_template_repo)


@pytest.fixture
def task_validator(mock_task_repo):
    """TaskValidator instance"""
    return TaskValidator(mock_task_repo)


@pytest.fixture
def template_service(mock_template_repo, template_validator):
    """TemplateService instance"""
    return TemplateService(mock_template_repo, template_validator)


@pytest.fixture
def mock_specialist_repo():
    """Mock SpecialistRepository"""
    repo = MagicMock()
    return repo


@pytest.fixture
def assignment_validator(mock_specialist_repo):
    """AssignmentValidator instance"""
    return AssignmentValidator()


@pytest.fixture
def task_gen_service(mock_task_repo, mock_template_repo, mock_instance_repo, task_validator):
    """TaskGenerationService instance"""
    return TaskGenerationService(mock_task_repo, mock_template_repo, mock_instance_repo, task_validator)


@pytest.fixture
def assignment_service(mock_specialist_repo, assignment_validator):
    """SpecialistAssignmentService instance"""
    return SpecialistAssignmentService(mock_specialist_repo, assignment_validator)


@pytest.fixture
def instance_service(mock_instance_repo, mock_template_repo, task_gen_service, assignment_service, instance_validator):
    """WorkflowInstanceService instance"""
    return WorkflowInstanceService(mock_instance_repo, mock_template_repo, task_gen_service, assignment_service, instance_validator)


@pytest.fixture
def sample_phase():
    """Sample Phase object"""
    return Phase(
        id=1,
        template_id=1,
        phase_key='phase1',
        phase_label='Phase 1',
        specialist_type='engineer',
        phase_order=1,
        is_parallel=False,
    )


@pytest.fixture
def sample_task_def():
    """Sample TaskDef object"""
    return TaskDef(
        id=1,
        phase_id=1,
        template_id=1,
        task_key='task1',
        task_title='Task 1',
        task_description='Task 1 description',
        depends_on_key=None,
        priority=1,
    )


@pytest.fixture
def sample_template():
    """Sample Template object"""
    return Template(
        id=1,
        name='Test Template',
        description='Test template',
        status='draft',
        created_by='test@example.com',
    )


@pytest.fixture
def sample_workflow_instance():
    """Sample WorkflowInstance object"""
    return WorkflowInstance(
        id=1,
        template_id=1,
        name='Test Workflow',
        status='active',
    )


@pytest.fixture
def sample_phase_instance():
    """Sample PhaseInstance object"""
    return PhaseInstance(
        id=1,
        instance_id=1,
        phase_key='phase1',
        status='pending',
    )


# ===== Shared Fixtures for All Test Levels =====

@pytest.fixture
def sample_agents():
    """Sample agents dict for shared use"""
    return {
        'alice': {'name': 'Alice Architect', 'email': 'alice@example.com', 'role': 'architect'},
        'bob': {'name': 'Bob Backend', 'email': 'bob@example.com', 'role': 'backend'},
        'carol': {'name': 'Carol Frontend', 'email': 'carol@example.com', 'role': 'frontend'},
    }


@pytest.fixture
def sample_phases():
    """Sample phases list (planning, development, testing)"""
    return [
        Phase(
            id=1,
            template_id=1,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1,
            is_parallel=False,
        ),
        Phase(
            id=2,
            template_id=1,
            phase_key='development',
            phase_label='Development',
            specialist_type='engineer',
            phase_order=2,
            is_parallel=False,
        ),
        Phase(
            id=3,
            template_id=1,
            phase_key='testing',
            phase_label='Testing',
            specialist_type='qa',
            phase_order=3,
            is_parallel=True,
        ),
    ]


@pytest.fixture
def sample_tasks():
    """Sample tasks list with dependencies"""
    return [
        DevTask(
            id=1,
            title='Requirements Analysis',
            description='Analyze project requirements',
            assignee='Alice Architect',
            phase='planning',
            workflow_instance_id=1,
            status='pending',
            priority=1,
            estimated_hours=8,
        ),
        DevTask(
            id=2,
            title='Architecture Design',
            description='Design system architecture',
            assignee='Alice Architect',
            phase='planning',
            workflow_instance_id=1,
            status='blocked',
            priority=2,
            estimated_hours=12,
        ),
        DevTask(
            id=3,
            title='Backend API Development',
            description='Develop backend API',
            assignee='Bob Backend',
            phase='development',
            workflow_instance_id=1,
            status='blocked',
            priority=1,
            estimated_hours=20,
        ),
        DevTask(
            id=4,
            title='Frontend UI Development',
            description='Build frontend interface',
            assignee='Carol Frontend',
            phase='development',
            workflow_instance_id=1,
            status='blocked',
            priority=2,
            estimated_hours=16,
        ),
        DevTask(
            id=5,
            title='Unit Tests',
            description='Write unit tests',
            assignee='Bob Backend',
            phase='testing',
            workflow_instance_id=1,
            status='blocked',
            priority=1,
            estimated_hours=12,
        ),
    ]


# ===== Integration Test Fixtures =====

@pytest.fixture
def mock_graph_repo():
    """Mock GraphRepository (KuzuDB)"""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_database():
    """Mock database connection for integration tests"""
    db = MagicMock()
    db.cursor = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.close = MagicMock()
    return db


@pytest.fixture
def integration_template_service(mock_database, mock_template_repo, template_validator):
    """TemplateService with mocked database"""
    return TemplateService(mock_template_repo, template_validator)


@pytest.fixture
def integration_instance_service(
    mock_database,
    mock_instance_repo,
    mock_template_repo,
    mock_task_repo,
    mock_specialist_repo,
    task_gen_service,
    assignment_service,
    instance_validator,
    mock_graph_repo,
):
    """WorkflowInstanceService with mocked database and graph"""
    return WorkflowInstanceService(
        mock_instance_repo,
        mock_template_repo,
        task_gen_service,
        assignment_service,
        instance_validator,
    )


# ===== E2E Test Fixtures =====

@pytest.fixture
def sample_template_with_phases(sample_template):
    """Template with nested phases for E2E tests"""
    phase1 = Phase(
        id=1,
        template_id=1,
        phase_key='planning',
        phase_label='Planning',
        specialist_type='pm',
        phase_order=1,
        is_parallel=False,
    )
    phase2 = Phase(
        id=2,
        template_id=1,
        phase_key='development',
        phase_label='Development',
        specialist_type='engineer',
        phase_order=2,
        is_parallel=False,
    )
    sample_template.phases = [phase1, phase2]
    return sample_template


@pytest.fixture
def sample_template_with_tasks(sample_template_with_phases):
    """Template with nested phases and tasks for E2E tests"""
    task1 = TaskDef(
        id=1,
        phase_id=1,
        template_id=1,
        task_key='plan_arch',
        task_title='Plan Architecture',
        task_description='Design system architecture',
        depends_on_key=None,
        priority=1,
    )
    task2 = TaskDef(
        id=2,
        phase_id=1,
        template_id=1,
        task_key='plan_db',
        task_title='Plan Database',
        task_description='Design database schema',
        depends_on_key='plan_arch',
        priority=2,
    )
    task3 = TaskDef(
        id=3,
        phase_id=2,
        template_id=1,
        task_key='impl_api',
        task_title='Implement API',
        task_description='Implement REST API',
        depends_on_key=None,
        priority=1,
    )
    sample_template_with_phases.phases[0].tasks = [task1, task2]
    sample_template_with_phases.phases[1].tasks = [task3]
    return sample_template_with_phases


@pytest.fixture
def sample_specialist_assignments():
    """Sample specialist assignments for E2E tests"""
    return {
        'planning': {'email': 'pm@example.com'},
        'development': {'email': 'engineer@example.com'},
    }


@pytest.fixture
def e2e_db_path(tmp_path):
    """Temporary database path for E2E tests"""
    return str(tmp_path / 'test_workflow.db')


@pytest.fixture
def e2e_template_service(e2e_db_path, mock_template_repo, template_validator):
    """TemplateService for E2E tests with temporary database"""
    return TemplateService(mock_template_repo, template_validator)


@pytest.fixture
def e2e_instance_service(
    e2e_db_path,
    mock_instance_repo,
    mock_template_repo,
    task_gen_service,
    assignment_service,
    instance_validator,
):
    """WorkflowInstanceService for E2E tests with temporary database"""
    return WorkflowInstanceService(
        mock_instance_repo,
        mock_template_repo,
        task_gen_service,
        assignment_service,
        instance_validator,
    )
