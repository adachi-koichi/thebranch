"""E2E/BDD test fixtures for workflow template system"""

import pytest
import sqlite3
from datetime import datetime
from pathlib import Path

from pytest_bdd import given, when, then, parsers

from workflow.db_schema import WORKFLOW_SCHEMA
from workflow.repositories.template import TemplateRepository
from workflow.repositories.instance import InstanceRepository
from workflow.repositories.task import TaskRepository
from workflow.repositories.specialist import SpecialistRepository
from workflow.validation.template import TemplateValidator
from workflow.validation.instance import InstanceValidator
from workflow.services.template import TemplateService
from workflow.services.instance import WorkflowInstanceService
from workflow.exceptions import SpecialistNotFoundError, ValidationError


def normalize_specialist_type(specialist_type_text: str) -> str:
	"""Convert human-readable specialist type to system code (e.g., 'Product Manager' -> 'pm')"""
	mapping = {
		'product manager': 'pm',
		'product_manager': 'pm',
		'pm': 'pm',
		'engineer': 'engineer',
		'qa engineer': 'qa',
		'qa_engineer': 'qa',
		'qa': 'qa',
		'devops': 'devops',
		'dev ops': 'devops',
		'dev_ops': 'devops',
		'architect': 'engineer',
	}
	normalized = specialist_type_text.lower().strip()
	return mapping.get(normalized, normalized)


# Import step definitions so pytest-bdd can discover them (after normalize_specialist_type is defined)
from tests.workflow.e2e.step_defs import template_steps  # noqa: F401
from tests.workflow.e2e.step_defs import instance_steps  # noqa: F401
from tests.workflow.e2e.step_defs import task_steps  # noqa: F401


@pytest.fixture(scope='function')
def temp_db(tmp_path):
    """Create temporary test database with schema"""
    db_path = tmp_path / "test_e2e.db"
    # Schema matching repository table names
    schema = '''
    CREATE TABLE IF NOT EXISTS workflow_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        status TEXT DEFAULT 'draft',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        created_by TEXT
    );

    CREATE TABLE IF NOT EXISTS wf_template_phases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        phase_key TEXT NOT NULL,
        phase_label TEXT NOT NULL,
        specialist_type TEXT NOT NULL,
        phase_order INTEGER NOT NULL,
        is_parallel INTEGER DEFAULT 0,
        task_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (template_id) REFERENCES workflow_templates(id),
        UNIQUE (template_id, phase_key)
    );

    CREATE TABLE IF NOT EXISTS wf_template_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phase_id INTEGER NOT NULL,
        template_id INTEGER NOT NULL,
        task_key TEXT NOT NULL,
        task_title TEXT NOT NULL,
        task_description TEXT,
        category TEXT,
        depends_on_key TEXT,
        priority INTEGER DEFAULT 1,
        estimated_hours REAL,
        task_order INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id),
        FOREIGN KEY (template_id) REFERENCES workflow_templates(id),
        UNIQUE (phase_id, task_key)
    );

    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        specialist_type TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS workflow_instances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        context TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        FOREIGN KEY (template_id) REFERENCES workflow_templates(id)
    );

    CREATE TABLE IF NOT EXISTS wf_instance_nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id INTEGER NOT NULL,
        phase_id INTEGER NOT NULL,
        phase_key TEXT NOT NULL,
        status TEXT DEFAULT 'waiting',
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (instance_id) REFERENCES workflow_instances(id),
        FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id),
        UNIQUE (instance_id, phase_key)
    );

    CREATE TABLE IF NOT EXISTS workflow_instance_specialists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id INTEGER NOT NULL,
        phase_id INTEGER NOT NULL,
        specialist_id INTEGER NOT NULL,
        specialist_slug TEXT NOT NULL,
        specialist_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (instance_id) REFERENCES workflow_instances(id),
        FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id),
        FOREIGN KEY (specialist_id) REFERENCES agents(id),
        UNIQUE (instance_id, phase_id)
    );

    CREATE TABLE IF NOT EXISTS dev_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        assignee TEXT NOT NULL,
        phase TEXT NOT NULL,
        workflow_instance_id INTEGER,
        wf_node_key TEXT,
        status TEXT DEFAULT 'blocked',
        priority INTEGER DEFAULT 1,
        estimated_hours REAL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        unblocked_at TEXT,
        FOREIGN KEY (workflow_instance_id) REFERENCES workflow_instances(id)
    );

    CREATE TABLE IF NOT EXISTS task_dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        predecessor_id INTEGER NOT NULL,
        successor_id INTEGER NOT NULL,
        dep_type TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (predecessor_id) REFERENCES dev_tasks(id),
        FOREIGN KEY (successor_id) REFERENCES dev_tasks(id),
        UNIQUE (predecessor_id, successor_id)
    );
    '''
    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema)
    conn.commit()
    yield str(db_path)
    conn.close()


@pytest.fixture(scope='function')
def template_repo(temp_db):
    """TemplateRepository with test database"""
    return TemplateRepository(temp_db)


@pytest.fixture(scope='function')
def instance_repo(temp_db):
    """InstanceRepository with test database"""
    return InstanceRepository(temp_db)


@pytest.fixture(scope='function')
def task_repo(temp_db):
    """TaskRepository with test database"""
    return TaskRepository(temp_db)


@pytest.fixture(scope='function')
def specialist_repo(temp_db):
    """SpecialistRepository with test database"""
    return SpecialistRepository(temp_db)


@pytest.fixture(scope='function')
def template_validator(template_repo):
    """TemplateValidator instance"""
    return TemplateValidator(template_repo)


@pytest.fixture(scope='function')
def instance_validator(instance_repo, template_repo):
    """InstanceValidator instance"""
    return InstanceValidator(instance_repo, template_repo)


@pytest.fixture(scope='function')
def template_service(template_repo, template_validator):
    """TemplateService instance"""
    return TemplateService(template_repo, template_validator)


class MockAssignmentService:
    """Mock specialist assignment service for testing"""
    def __init__(self, specialist_repo):
        self.specialist_repo = specialist_repo

    def validate_and_resolve_assignments(self, template_id: int, assignments: dict) -> dict:
        """Mock validation - convert emails to specialist objects"""
        resolved = {}
        for phase_key, email in assignments.items():
            specialist = self.specialist_repo.get_agent_by_email(email)
            if specialist:
                resolved[phase_key] = specialist
            else:
                resolved[phase_key] = None
        return resolved


class MockTaskGenService:
    """Mock task generation service for testing"""
    def __init__(self, template_repo, instance_repo, task_repo, specialist_repo):
        self.template_repo = template_repo
        self.instance_repo = instance_repo
        self.task_repo = task_repo
        self.specialist_repo = specialist_repo

    def generate_tasks_for_instance(self, instance_id: int, template_id: int) -> int:
        """Generate tasks from template for instance"""
        instance = self.instance_repo.get_instance(instance_id)
        phases = self.template_repo.get_phases(template_id)

        total_tasks = 0
        for phase in phases:
            task_defs = self.template_repo.get_tasks_for_phase(phase.id)
            specialist = self.instance_repo.get_phase_specialist(instance_id, phase.id)

            for task_def in task_defs:
                self.task_repo.create_task(
                    title=task_def.task_title,
                    description=task_def.task_description or "",
                    assignee=specialist.email if specialist else "unknown@example.com",
                    phase=phase.phase_key,
                    workflow_instance_id=instance_id,
                    wf_node_key=f"{phase.phase_key}_{task_def.task_key}",
                    status='blocked',
                    priority=task_def.priority or 1,
                    estimated_hours=task_def.estimated_hours or 0
                )
                total_tasks += 1

        return total_tasks


@pytest.fixture(scope='function')
def instance_service(instance_repo, template_repo, instance_validator, specialist_repo, task_repo):
    """WorkflowInstanceService instance"""
    return WorkflowInstanceService(
        instance_repo=instance_repo,
        template_repo=template_repo,
        task_gen_service=MockTaskGenService(template_repo, instance_repo, task_repo, specialist_repo),
        assignment_svc=MockAssignmentService(specialist_repo),
        validator=instance_validator,
    )


class BDDContext:
    """Shared context for BDD steps"""
    def __init__(self):
        self.templates = {}
        self.instances = {}
        self.phases = {}
        self.tasks = {}
        self.specialists = {}
        self.specialist_assignments = {}
        self.specialist_assignments_dict = {}
        self.generated_tasks = []
        self.workflow_instance = None
        self.task_generation_triggered = False
        self.current_template_name = None


@pytest.fixture(scope='function')
def bdd_context():
    """BDD test context"""
    return BDDContext()


@pytest.fixture
def table(request):
    """Pytest-bdd table fixture - extracts tables from Gherkin feature file"""
    import os
    from pathlib import Path

    try:
        # Get the feature file path
        test_file = Path(__file__).parent
        feature_file = test_file / ".." / ".." / ".." / "features" / "workflow-template.feature"

        if not feature_file.exists():
            return []

        # Parse feature file to find tables
        with open(feature_file) as f:
            content = f.read()

        # Get the test name to find the corresponding scenario
        test_name = request.node.name

        # Map test names to scenario names
        scenario_map = {
            'test_create_workflow_template': 'Create workflow template with phases and task definitions',
            'test_instantiate_template': 'Instantiate template to workflow instance with specialist assignment',
            'test_auto_generate_tasks': 'Auto-generate phase-based tasks from template',
            'test_reuse_template': 'Reuse existing template and reassign specialists',
            'test_specialist_validation_error': 'Validation error when specialist not available',
            'test_multiple_specialists': 'Multiple specialists assigned to same phase',
        }

        scenario_name = scenario_map.get(test_name)
        if not scenario_name:
            return []

        # Simple parsing to find scenario and extract tables
        lines = content.split('\n')
        in_scenario = False
        tables = []
        current_table = None
        table_header = None

        for i, line in enumerate(lines):
            # Check if we're in the target scenario
            if f'Scenario: {scenario_name}' in line:
                in_scenario = True
                tables = []
                current_table = None
                continue

            # Check if we've moved to a new scenario
            if in_scenario and line.strip().startswith('Scenario:'):
                break

            if in_scenario:
                # Check for table header
                if line.strip().startswith('|'):
                    if current_table is None:
                        # This is a new table header
                        headers = [h.strip() for h in line.split('|')[1:-1]]
                        table_header = headers
                        current_table = []
                    elif table_header:
                        # This is a table row
                        row_values = [v.strip() for v in line.split('|')[1:-1]]
                        row_dict = dict(zip(table_header, row_values))
                        current_table.append(row_dict)
                elif current_table is not None and not line.strip().startswith('|'):
                    # End of current table
                    if current_table:
                        tables.append(current_table)
                    current_table = None
                    table_header = None

        # Add the last table if any
        if current_table:
            tables.append(current_table)

        # Track which table we're on for this test
        table_index_key = f"{test_name}_table_index"
        if not hasattr(request.session.config, '_table_indices'):
            request.session.config._table_indices = {}

        if table_index_key not in request.session.config._table_indices:
            request.session.config._table_indices[table_index_key] = 0

        table_idx = request.session.config._table_indices[table_index_key]
        request.session.config._table_indices[table_index_key] += 1

        if table_idx < len(tables):
            return tables[table_idx]
    except Exception as e:
        pass

    return []
