"""BDD test fixtures for workflow management system"""

import pytest
import sqlite3
from datetime import datetime
from pathlib import Path

from workflow.db_schema import WORKFLOW_SCHEMA
from workflow.repositories.template import TemplateRepository
from workflow.repositories.instance import InstanceRepository
from workflow.repositories.task import TaskRepository
from workflow.repositories.specialist import SpecialistRepository
from workflow.validation.template import TemplateValidator
from workflow.validation.instance import InstanceValidator
from workflow.services.template import TemplateService
from workflow.services.instance import WorkflowInstanceService


@pytest.fixture(scope='function')
def temp_db(tmp_path):
  """Create temporary test database with full schema"""
  db_path = tmp_path / "test_bdd.db"

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

  CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    change_delta TEXT,
    created_at TEXT NOT NULL
  );
  '''

  conn = sqlite3.connect(str(db_path))
  conn.executescript(schema)
  conn.commit()
  yield str(db_path)
  conn.close()


@pytest.fixture(scope='function')
def template_repo(temp_db):
  return TemplateRepository(temp_db)


@pytest.fixture(scope='function')
def instance_repo(temp_db):
  return InstanceRepository(temp_db)


@pytest.fixture(scope='function')
def task_repo(temp_db):
  return TaskRepository(temp_db)


@pytest.fixture(scope='function')
def specialist_repo(temp_db):
  return SpecialistRepository(temp_db)


@pytest.fixture(scope='function')
def template_validator(template_repo):
  return TemplateValidator(template_repo)


@pytest.fixture(scope='function')
def instance_validator(instance_repo, template_repo):
  return InstanceValidator(instance_repo, template_repo)


@pytest.fixture(scope='function')
def template_service(template_repo, template_validator):
  return TemplateService(template_repo, template_validator)


class MockAssignmentService:
  def __init__(self, specialist_repo):
    self.specialist_repo = specialist_repo

  def validate_and_resolve_assignments(self, template_id: int, assignments: dict) -> dict:
    resolved = {}
    for phase_key, email in assignments.items():
      specialist = self.specialist_repo.get_agent_by_email(email)
      resolved[phase_key] = specialist
    return resolved


class MockTaskGenService:
  def __init__(self, template_repo, instance_repo, task_repo, specialist_repo):
    self.template_repo = template_repo
    self.instance_repo = instance_repo
    self.task_repo = task_repo
    self.specialist_repo = specialist_repo

  def generate_tasks_for_instance(self, instance_id: int, template_id: int) -> int:
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
  return WorkflowInstanceService(
    instance_repo=instance_repo,
    template_repo=template_repo,
    task_gen_service=MockTaskGenService(template_repo, instance_repo, task_repo, specialist_repo),
    assignment_svc=MockAssignmentService(specialist_repo),
    validator=instance_validator,
  )


class BDDContext:
  """Shared context for BDD scenarios"""
  def __init__(self):
    self.templates = {}
    self.instances = {}
    self.phases = {}
    self.tasks = {}
    self.specialists = {}
    self.specialist_assignments = {}
    self.generated_tasks = []
    self.workflow_instance = None
    self.current_template = None
    self.current_instance = None
    self.validation_errors = []
    self.task_count = 0


@pytest.fixture(scope='function')
def bdd_context():
  return BDDContext()


class Table:
  """Gherkin table wrapper"""
  def __init__(self, rows=None):
    self.rows = rows or []

  def __iter__(self):
    return iter(self.rows)

  def __len__(self):
    return len(self.rows)
