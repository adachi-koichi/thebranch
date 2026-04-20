"""Unit test fixtures for workflow module"""

from unittest.mock import Mock, MagicMock
from datetime import datetime
import pytest

from workflow.models import Template, Phase, TaskDef, Agent
from workflow.models.instance import WorkflowInstance, PhaseInstance
from workflow.models.task import DevTask, TaskDependency
from workflow.validation.template import TemplateValidator
from workflow.validation.instance import InstanceValidator
from workflow.validation.task import TaskValidator
from workflow.validation.assignment import AssignmentValidator
from workflow.services.template import TemplateService
from workflow.services.instance import WorkflowInstanceService
from workflow.services.task_gen import TaskGenerationService
from workflow.services.assignment import SpecialistAssignmentService


# ===== MOCK REPOSITORIES =====

@pytest.fixture
def template_repo_mock():
    """Mock TemplateRepository"""
    return Mock()


@pytest.fixture
def instance_repo_mock():
    """Mock InstanceRepository"""
    return Mock()


@pytest.fixture
def task_repo_mock():
    """Mock TaskRepository"""
    return Mock()


@pytest.fixture
def specialist_repo_mock():
    """Mock SpecialistRepository"""
    return Mock()


@pytest.fixture
def graph_repo_mock():
    """Mock GraphRepository"""
    return Mock()


# ===== MOCK VALIDATORS =====

@pytest.fixture
def validator_mock():
    """Mock Validator"""
    return Mock()


@pytest.fixture
def template_validator_mock():
    """Mock TemplateValidator"""
    return Mock()


@pytest.fixture
def instance_validator_mock():
    """Mock InstanceValidator"""
    return Mock()


@pytest.fixture
def task_validator_mock():
    """Mock TaskValidator"""
    return Mock()


@pytest.fixture
def assignment_validator_mock():
    """Mock AssignmentValidator"""
    return Mock()


# ===== REAL VALIDATORS (for unit tests) =====

@pytest.fixture
def template_validator(template_repo_mock):
    """TemplateValidator instance"""
    return TemplateValidator(template_repo_mock)


@pytest.fixture
def instance_validator(instance_repo_mock, template_repo_mock):
    """InstanceValidator instance"""
    return InstanceValidator(instance_repo_mock, template_repo_mock)


@pytest.fixture
def task_validator(task_repo_mock):
    """TaskValidator instance"""
    return TaskValidator(task_repo_mock)


@pytest.fixture
def assignment_validator(specialist_repo_mock):
    """AssignmentValidator instance"""
    return AssignmentValidator(specialist_repo_mock)


# ===== SERVICES =====

@pytest.fixture
def template_service(template_repo_mock, template_validator_mock):
    """TemplateService instance"""
    return TemplateService(template_repo_mock, template_validator_mock)


@pytest.fixture
def instance_service(
    instance_repo_mock,
    template_repo_mock,
    task_repo_mock,
    specialist_repo_mock,
    instance_validator_mock,
):
    """WorkflowInstanceService instance"""
    task_gen_svc = TaskGenerationService(
        task_repo_mock, template_repo_mock, instance_repo_mock, task_validator_mock
    )
    assignment_svc = SpecialistAssignmentService(specialist_repo_mock, assignment_validator_mock)
    return WorkflowInstanceService(
        instance_repo_mock,
        template_repo_mock,
        task_gen_svc,
        assignment_svc,
        instance_validator_mock,
    )


@pytest.fixture
def task_gen_service(task_repo_mock, template_repo_mock, instance_repo_mock, task_validator_mock):
    """TaskGenerationService instance"""
    return TaskGenerationService(task_repo_mock, template_repo_mock, instance_repo_mock, task_validator_mock)


@pytest.fixture
def assignment_service(specialist_repo_mock, assignment_validator_mock):
    """SpecialistAssignmentService instance"""
    return SpecialistAssignmentService(specialist_repo_mock, assignment_validator_mock)


# ===== SAMPLE DATA =====

@pytest.fixture
def sample_template():
    """Sample Template"""
    return Template(
        id=1,
        name="Product Launch",
        description="Standard product launch process",
        status="draft",
        created_by="alice@example.com",
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_phases():
    """Sample phases list"""
    return [
        Phase(
            id=1,
            template_id=1,
            phase_key="planning",
            phase_label="Planning",
            specialist_type="pm",
            phase_order=1,
            is_parallel=False,
        ),
        Phase(
            id=2,
            template_id=1,
            phase_key="development",
            phase_label="Development",
            specialist_type="engineer",
            phase_order=2,
            is_parallel=False,
        ),
        Phase(
            id=3,
            template_id=1,
            phase_key="testing",
            phase_label="Testing",
            specialist_type="qa",
            phase_order=3,
            is_parallel=False,
        ),
    ]


@pytest.fixture
def sample_task_defs():
    """Sample task definitions"""
    return [
        TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key="design-arch",
            task_title="Design {phase_label} Architecture",
            task_description="Create architecture with {specialist_name}",
            priority=1,
            estimated_hours=8,
            task_order=1,
        ),
        TaskDef(
            id=2,
            phase_id=1,
            template_id=1,
            task_key="requirements",
            task_title="Prepare {phase_label} Requirements",
            task_description="Document requirements",
            priority=2,
            estimated_hours=6,
            task_order=2,
        ),
        TaskDef(
            id=3,
            phase_id=2,
            template_id=1,
            task_key="implement",
            task_title="Implement Features",
            task_description="Implement features",
            priority=1,
            estimated_hours=16,
            task_order=1,
            depends_on_key="requirements",
        ),
    ]


@pytest.fixture
def sample_workflow_instance():
    """Sample WorkflowInstance"""
    return WorkflowInstance(
        id=1,
        template_id=1,
        name="Product Launch #1",
        status="ready",
        context={"version": "1.0"},
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_agents():
    """Sample agents"""
    return {
        "alice": Agent(
            id=1,
            name="Alice Johnson",
            email="alice@example.com",
            specialist_type="pm",
        ),
        "bob": Agent(
            id=2,
            name="Bob Smith",
            email="bob@example.com",
            specialist_type="engineer",
        ),
        "carol": Agent(
            id=3,
            name="Carol Davis",
            email="carol@example.com",
            specialist_type="qa",
        ),
    }


@pytest.fixture
def sample_dev_tasks():
    """Sample dev tasks"""
    return [
        DevTask(
            id=1,
            title="Design Planning Architecture",
            description="Create architecture with Alice Johnson",
            assignee="alice@example.com",
            phase="planning",
            workflow_instance_id=1,
            wf_node_key="planning",
            status="blocked",
            priority=1,
            estimated_hours=8,
        ),
        DevTask(
            id=2,
            title="Implement Backend API",
            description="Implement backend API",
            assignee="bob@example.com",
            phase="development",
            workflow_instance_id=1,
            wf_node_key="development",
            status="blocked",
            priority=1,
            estimated_hours=16,
        ),
    ]
