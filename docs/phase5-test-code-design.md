# Phase 5: ワークフローテンプレートシステム - テストコード設計

**作成日**: 2026-04-18  
**バージョン**: v1.0 (Phase 5 - Test Strategy)  
**参照**: phase4-detailed-interface-design.md

---

## 目次

1. [テスト戦略概要](#1-テスト戦略概要)
2. [ユニットテスト設計](#2-ユニットテスト設計)
3. [統合テスト設計](#3-統合テスト設計)
4. [E2E テスト & BDD ステップ定義](#4-e2e-テスト--bdd-ステップ定義)
5. [テスト DB 環境セットアップ](#5-テスト-db-環境セットアップ)
6. [テスト実行パイプライン](#6-テスト実行パイプライン)
7. [カバレッジ目標](#7-カバレッジ目標)

---

## 1. テスト戦略概要

### 1-1. テストピラミッド

```
        ▲
       /|\
      / | \  E2E Tests (BDD)
     /  |  \ - Full workflow scenarios
    /   |   \ - 5-10 tests
   /────┼────\
  /     |     \ Integration Tests
 /      |      \ - Module interactions
/       |       \ - 15-20 tests
/────────┼────────\
         |
    Unit Tests
  - Individual methods
  - 50-80 tests

Coverage Target:
- Unit: >80%
- Integration: >70%
- E2E: >60%
```

### 1-2. テストフレームワーク

| レイヤー | フレームワーク | ファイル | 実行方法 |
|---------|--------------|--------|--------|
| **Unit** | pytest | `tests/workflow/unit/` | `pytest tests/workflow/unit/` |
| **Integration** | pytest | `tests/workflow/integration/` | `pytest tests/workflow/integration/` |
| **E2E/BDD** | pytest-bdd | `tests/workflow/e2e/` | `pytest tests/workflow/e2e/ --feature` |

### 1-3. テスト環境

```
┌─────────────────────────────────────────┐
│ Test Environment (Ephemeral)            │
├─────────────────────────────────────────┤
│ SQLite (in-memory or temp file)         │
│ └─ :memory: for unit/integration tests  │
│ └─ /tmp/test-{timestamp}.db for E2E    │
│                                         │
│ KuzuDB (in-process)                    │
│ └─ Temporary graph database             │
│                                         │
│ Test Fixtures                           │
│ └─ Sample templates, instances, tasks   │
└─────────────────────────────────────────┘
```

---

## 2. ユニットテスト設計

### 2-1. テストファイル構成

```
tests/workflow/unit/
├── __init__.py
├── conftest.py                          # Shared fixtures
├── test_template_service.py             # TemplateService tests
├── test_template_repository.py          # TemplateRepository tests
├── test_instance_service.py             # WorkflowInstanceService tests
├── test_instance_repository.py          # InstanceRepository tests
├── test_task_gen_service.py             # TaskGenerationService tests
├── test_task_repository.py              # TaskRepository tests
├── test_assignment_service.py           # SpecialistAssignmentService tests
├── test_specialist_repository.py        # SpecialistRepository tests
└── test_validators.py                   # All validators
```

### 2-2. TemplateService テスト例

```python
# tests/workflow/unit/test_template_service.py

import pytest
from datetime import datetime
from workflow.services.template import TemplateService
from workflow.repositories.template import TemplateRepository
from workflow.validation.template import TemplateValidator
from workflow.exceptions import (
    ValidationError,
    TemplateNotFoundError,
    CircularDependencyError
)
from workflow.models.template import Template, Phase, TaskDef

class TestTemplateServiceCreateTemplate:
    """Test create_template() method"""
    
    @pytest.fixture
    def svc(self, template_repo_mock, validator_mock):
        """Initialize service with mocks"""
        return TemplateService(template_repo_mock, validator_mock)
    
    def test_create_template_valid(self, svc, template_repo_mock):
        """Create template with valid inputs"""
        # Arrange
        expected = Template(
            id=1,
            name="Product Launch",
            description="Standard product launch process",
            status='draft',
            created_by="alice@example.com",
            created_at=datetime.now()
        )
        template_repo_mock.create_template.return_value = expected
        
        # Act
        result = svc.create_template(
            name="Product Launch",
            description="Standard product launch process",
            created_by="alice@example.com"
        )
        
        # Assert
        assert result.id == 1
        assert result.name == "Product Launch"
        assert result.status == 'draft'
        template_repo_mock.create_template.assert_called_once()
    
    def test_create_template_empty_name(self, svc):
        """Create template with empty name → ValidationError"""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            svc.create_template(name="")
        
        assert "Invalid template name" in str(exc_info.value)
    
    def test_create_template_name_too_long(self, svc):
        """Create template with name >255 chars → ValidationError"""
        # Act & Assert
        with pytest.raises(ValidationError):
            svc.create_template(name="x" * 256)


class TestTemplateServiceAddPhase:
    """Test add_phase() method"""
    
    @pytest.fixture
    def svc(self, template_repo_mock, validator_mock):
        return TemplateService(template_repo_mock, validator_mock)
    
    def test_add_phase_valid(self, svc, template_repo_mock, validator_mock):
        """Add phase with valid inputs"""
        # Arrange
        template_repo_mock.get_template.return_value = Template(
            id=1, name="Product Launch", status='draft'
        )
        expected_phase = Phase(
            id=1, template_id=1, phase_key='planning',
            phase_label='Planning', specialist_type='pm',
            phase_order=1, is_parallel=False
        )
        template_repo_mock.create_phase.return_value = expected_phase
        
        # Act
        result = svc.add_phase(
            template_id=1,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1
        )
        
        # Assert
        assert result.id == 1
        assert result.phase_key == 'planning'
        validator_mock.validate_phase.assert_called_once()
    
    def test_add_phase_template_not_found(self, svc, template_repo_mock):
        """Add phase to non-existent template → TemplateNotFoundError"""
        template_repo_mock.get_template.return_value = None
        
        with pytest.raises(TemplateNotFoundError):
            svc.add_phase(
                template_id=999,
                phase_key='planning',
                phase_label='Planning',
                specialist_type='pm',
                phase_order=1
            )
    
    def test_add_phase_not_draft(self, svc, template_repo_mock):
        """Add phase to published template → ValidationError"""
        template_repo_mock.get_template.return_value = Template(
            id=1, name="Product Launch", status='published'
        )
        
        with pytest.raises(ValidationError) as exc_info:
            svc.add_phase(
                template_id=1,
                phase_key='planning',
                phase_label='Planning',
                specialist_type='pm',
                phase_order=1
            )
        
        assert "Cannot add phase to non-draft" in str(exc_info.value)
    
    def test_add_phase_duplicate_key(self, svc, template_repo_mock, validator_mock):
        """Add phase with duplicate phase_key → ValidationError"""
        template_repo_mock.get_template.return_value = Template(
            id=1, name="Product Launch", status='draft'
        )
        validator_mock.validate_phase.side_effect = ValidationError(
            "Phase key already exists"
        )
        
        with pytest.raises(ValidationError):
            svc.add_phase(
                template_id=1,
                phase_key='planning',
                phase_label='Planning',
                specialist_type='pm',
                phase_order=1
            )


class TestTemplateServicePublish:
    """Test publish_template() method"""
    
    @pytest.fixture
    def svc(self, template_repo_mock, validator_mock):
        return TemplateService(template_repo_mock, validator_mock)
    
    def test_publish_valid_template(self, svc, template_repo_mock, validator_mock):
        """Publish template with phases and tasks"""
        # Arrange
        template = Template(id=1, name="Product Launch", status='draft')
        template_repo_mock.get_template.return_value = template
        validator_mock.validate_template_complete.return_value = None
        
        # Act
        result = svc.publish_template(1)
        
        # Assert
        assert result.status == 'published'
        template_repo_mock.update_template.assert_called_once()
        validator_mock.validate_template_complete.assert_called_once()
    
    def test_publish_already_published(self, svc, template_repo_mock):
        """Publish already-published template → ValidationError"""
        template_repo_mock.get_template.return_value = Template(
            id=1, name="Product Launch", status='published'
        )
        
        with pytest.raises(ValidationError) as exc_info:
            svc.publish_template(1)
        
        assert "Cannot publish non-draft" in str(exc_info.value)
    
    def test_publish_incomplete_template(self, svc, template_repo_mock, validator_mock):
        """Publish template without phases → ValidationError"""
        template_repo_mock.get_template.return_value = Template(
            id=1, name="Product Launch", status='draft'
        )
        validator_mock.validate_template_complete.side_effect = ValidationError(
            "Template has no phases"
        )
        
        with pytest.raises(ValidationError):
            svc.publish_template(1)


class TestTemplateValidator:
    """Test TemplateValidator"""
    
    @pytest.fixture
    def validator(self, template_repo_mock):
        return TemplateValidator(template_repo_mock)
    
    def test_validate_phase_valid(self, validator):
        """Validate phase with valid inputs"""
        # Should not raise
        validator.validate_phase(
            template_id=1,
            phase_key='planning',
            specialist_type='pm',
            phase_order=1
        )
    
    def test_validate_phase_invalid_type(self, validator):
        """Validate phase with invalid specialist_type → ValidationError"""
        with pytest.raises(ValidationError):
            validator.validate_phase(
                template_id=1,
                phase_key='planning',
                specialist_type='invalid_type',
                phase_order=1
            )
    
    def test_validate_circular_dependency(self, validator, template_repo_mock):
        """Detect circular dependency in depends_on_key"""
        # Task A → B → C → A (circular)
        task_a = TaskDef(id=1, task_key='task_a', depends_on_key='task_c')
        task_b = TaskDef(id=2, task_key='task_b', depends_on_key='task_a')
        task_c = TaskDef(id=3, task_key='task_c', depends_on_key='task_b')
        
        # Graph should detect cycle
        with pytest.raises(CircularDependencyError) as exc_info:
            # Would be called during template_complete validation
            # Assuming validator has access to tasks
            validator.validate_no_circular_deps([task_a, task_b, task_c])
        
        assert "Circular dependency" in str(exc_info.value)
```

### 2-3. Fixtures (conftest.py)

```python
# tests/workflow/unit/conftest.py

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime
from workflow.models.template import Template, Phase, TaskDef
from workflow.models.instance import WorkflowInstance, PhaseInstance
from workflow.models.task import DevTask, TaskDependency
from workflow.models.specialist import Agent, SpecialistAssignment

# ===== MOCK REPOSITORIES =====

@pytest.fixture
def template_repo_mock():
    """Mock TemplateRepository"""
    mock = Mock()
    return mock

@pytest.fixture
def instance_repo_mock():
    """Mock InstanceRepository"""
    mock = Mock()
    return mock

@pytest.fixture
def task_repo_mock():
    """Mock TaskRepository"""
    mock = Mock()
    return mock

@pytest.fixture
def specialist_repo_mock():
    """Mock SpecialistRepository"""
    mock = Mock()
    return mock

@pytest.fixture
def graph_repo_mock():
    """Mock GraphRepository"""
    mock = Mock()
    return mock

# ===== MOCK VALIDATORS =====

@pytest.fixture
def validator_mock():
    """Mock Validator"""
    mock = Mock()
    return mock

# ===== TEST DATA FACTORIES =====

@pytest.fixture
def sample_template():
    """Sample template"""
    return Template(
        id=1,
        name="Product Launch",
        description="Standard product launch process",
        status='draft',
        created_by="alice@example.com",
        created_at=datetime.now()
    )

@pytest.fixture
def sample_phases():
    """Sample phases for template"""
    return [
        Phase(
            id=1, template_id=1, phase_key='planning',
            phase_label='Planning', specialist_type='pm',
            phase_order=1, is_parallel=False, task_count=3
        ),
        Phase(
            id=2, template_id=1, phase_key='development',
            phase_label='Development', specialist_type='engineer',
            phase_order=2, is_parallel=False, task_count=5
        ),
        Phase(
            id=3, template_id=1, phase_key='testing',
            phase_label='Testing', specialist_type='qa',
            phase_order=3, is_parallel=False, task_count=4
        ),
        Phase(
            id=4, template_id=1, phase_key='deployment',
            phase_label='Deployment', specialist_type='devops',
            phase_order=4, is_parallel=False, task_count=2
        ),
    ]

@pytest.fixture
def sample_tasks_for_phase():
    """Sample task definitions for a phase"""
    return [
        TaskDef(
            id=1, phase_id=1, template_id=1,
            task_key='design-arch', task_title='Design {phase_label} Architecture',
            task_description='Create architecture with {specialist_name}',
            priority=1, estimated_hours=8, task_order=1
        ),
        TaskDef(
            id=2, phase_id=1, template_id=1,
            task_key='requirements', task_title='Prepare {phase_label} Requirements',
            task_description='Document requirements',
            priority=2, estimated_hours=6, task_order=2
        ),
        TaskDef(
            id=3, phase_id=1, template_id=1,
            task_key='timeline', task_title='Create Launch Timeline',
            task_description='Plan timeline for {workflow_name}',
            priority=3, estimated_hours=4, task_order=3
        ),
    ]

@pytest.fixture
def sample_workflow_instance():
    """Sample workflow instance"""
    return WorkflowInstance(
        id=42,
        template_id=1,
        name="Product Launch #1",
        status='ready',
        context={'version': '1.0'},
        created_at=datetime.now()
    )

@pytest.fixture
def sample_agents():
    """Sample agents/specialists"""
    return {
        'alice': Agent(id=1, name='Alice Johnson', email='alice@example.com', specialist_type='pm'),
        'bob': Agent(id=2, name='Bob Smith', email='bob@example.com', specialist_type='engineer'),
        'carol': Agent(id=3, name='Carol Davis', email='carol@example.com', specialist_type='qa'),
        'dave': Agent(id=7, name='Dave Wilson', email='dave@example.com', specialist_type='devops'),
    }

@pytest.fixture
def sample_tasks():
    """Sample dev_tasks"""
    return [
        DevTask(
            id=101, title='Design Planning Architecture',
            description='Create architecture with Alice Johnson',
            assignee='alice@example.com', phase='planning',
            workflow_instance_id=42, wf_node_key='planning',
            status='blocked', priority=1, estimated_hours=8
        ),
        DevTask(
            id=102, title='Implement Backend API',
            description='Implement backend API',
            assignee='bob@example.com', phase='development',
            workflow_instance_id=42, wf_node_key='development',
            status='blocked', priority=1, estimated_hours=16
        ),
    ]
```

---

## 3. 統合テスト設計

### 3-1. テストファイル構成

```
tests/workflow/integration/
├── __init__.py
├── conftest.py                          # DB fixtures, real DB setup
├── test_template_workflow.py            # Template lifecycle
├── test_instantiation_workflow.py       # Full instantiation
├── test_task_generation_workflow.py     # Task generation flow
├── test_dependency_resolution.py        # Dependency handling
└── test_error_scenarios.py              # Error cases
```

### 3-2. 統合テスト例

```python
# tests/workflow/integration/test_instantiation_workflow.py

import pytest
import sqlite3
from datetime import datetime
from workflow.services.template import TemplateService
from workflow.services.instance import WorkflowInstanceService
from workflow.services.task_gen import TaskGenerationService
from workflow.services.assignment import SpecialistAssignmentService
from workflow.repositories.template import TemplateRepository
from workflow.repositories.instance import InstanceRepository
from workflow.repositories.task import TaskRepository
from workflow.repositories.specialist import SpecialistRepository
from workflow.repositories.graph import GraphRepository
from workflow.exceptions import (
    ValidationError,
    SpecialistNotFoundError,
    CircularDependencyError
)

class TestInstantiationWorkflow:
    """Integration tests for full instantiation flow"""
    
    @pytest.fixture
    def real_db(self, tmp_path):
        """Create real SQLite test database"""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        
        # Initialize schema
        conn.executescript("""
            CREATE TABLE workflow_templates (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'draft',
                created_by TEXT,
                created_at DATETIME,
                updated_at DATETIME
            );
            
            CREATE TABLE wf_template_phases (
                id INTEGER PRIMARY KEY,
                template_id INTEGER,
                phase_key TEXT,
                phase_label TEXT,
                specialist_type TEXT,
                phase_order INTEGER,
                is_parallel BOOLEAN DEFAULT 0,
                task_count INTEGER DEFAULT 0,
                created_at DATETIME,
                FOREIGN KEY (template_id) REFERENCES workflow_templates(id)
            );
            
            CREATE TABLE wf_template_tasks (
                id INTEGER PRIMARY KEY,
                phase_id INTEGER,
                template_id INTEGER,
                task_key TEXT,
                task_title TEXT,
                task_description TEXT,
                category TEXT,
                depends_on_key TEXT,
                priority INTEGER DEFAULT 1,
                estimated_hours FLOAT,
                task_order INTEGER DEFAULT 0,
                created_at DATETIME,
                FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id),
                FOREIGN KEY (template_id) REFERENCES workflow_templates(id)
            );
            
            CREATE TABLE workflow_instances (
                id INTEGER PRIMARY KEY,
                template_id INTEGER,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                context TEXT,
                created_at DATETIME,
                started_at DATETIME,
                completed_at DATETIME,
                FOREIGN KEY (template_id) REFERENCES workflow_templates(id)
            );
            
            CREATE TABLE workflow_instance_specialists (
                id INTEGER PRIMARY KEY,
                instance_id INTEGER,
                phase_id INTEGER,
                specialist_id INTEGER,
                specialist_slug TEXT,
                specialist_name TEXT,
                created_at DATETIME,
                FOREIGN KEY (instance_id) REFERENCES workflow_instances(id),
                FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id)
            );
            
            CREATE TABLE dev_tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                assignee TEXT,
                phase TEXT,
                workflow_instance_id INTEGER,
                wf_node_key TEXT,
                status TEXT DEFAULT 'blocked',
                priority INTEGER DEFAULT 1,
                estimated_hours FLOAT,
                created_at DATETIME,
                started_at DATETIME,
                completed_at DATETIME,
                unblocked_at DATETIME,
                FOREIGN KEY (workflow_instance_id) REFERENCES workflow_instances(id)
            );
            
            CREATE TABLE task_dependencies (
                id INTEGER PRIMARY KEY,
                predecessor_id INTEGER,
                successor_id INTEGER,
                dep_type TEXT,
                created_at DATETIME,
                FOREIGN KEY (predecessor_id) REFERENCES dev_tasks(id),
                FOREIGN KEY (successor_id) REFERENCES dev_tasks(id)
            );
            
            CREATE TABLE agents (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT UNIQUE,
                specialist_type TEXT,
                created_at DATETIME
            );
        """)
        
        conn.commit()
        yield conn
        conn.close()
    
    @pytest.fixture
    def repos(self, real_db):
        """Initialize repositories with real DB"""
        return {
            'template': TemplateRepository(real_db),
            'instance': InstanceRepository(real_db),
            'task': TaskRepository(real_db),
            'specialist': SpecialistRepository(real_db),
            'graph': GraphRepository(real_db),
        }
    
    @pytest.fixture
    def services(self, repos):
        """Initialize services with repositories"""
        return {
            'template': TemplateService(repos['template'], Mock()),
            'instance': WorkflowInstanceService(
                repos['instance'], repos['template'],
                Mock(), Mock(), Mock()
            ),
            'task_gen': TaskGenerationService(
                repos['task'], repos['template'],
                repos['instance'], repos['graph'], Mock()
            ),
            'assignment': SpecialistAssignmentService(
                repos['specialist'], Mock()
            ),
        }
    
    def test_full_instantiation_workflow(self, repos, services, real_db):
        """
        Full E2E: Create template → Publish → Instantiate → Verify tasks
        """
        # Setup: Create agents
        alice = repos['specialist'].create_agent(
            name='Alice Johnson', email='alice@example.com',
            specialist_type='pm'
        )
        bob = repos['specialist'].create_agent(
            name='Bob Smith', email='bob@example.com',
            specialist_type='engineer'
        )
        carol = repos['specialist'].create_agent(
            name='Carol Davis', email='carol@example.com',
            specialist_type='qa'
        )
        dave = repos['specialist'].create_agent(
            name='Dave Wilson', email='dave@example.com',
            specialist_type='devops'
        )
        
        # Step 1: Create template
        template = services['template'].create_template(
            name="Product Launch",
            description="Standard product launch process",
            created_by="alice@example.com"
        )
        assert template.id is not None
        
        # Step 2: Add phases
        phase_planning = services['template'].add_phase(
            template_id=template.id,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1
        )
        
        phase_dev = services['template'].add_phase(
            template_id=template.id,
            phase_key='development',
            phase_label='Development',
            specialist_type='engineer',
            phase_order=2
        )
        
        phase_qa = services['template'].add_phase(
            template_id=template.id,
            phase_key='testing',
            phase_label='Testing',
            specialist_type='qa',
            phase_order=3
        )
        
        # Step 3: Add tasks to phases
        services['template'].add_task_to_phase(
            phase_id=phase_planning.id,
            task_key='design-arch',
            task_title='Design {phase_label} Architecture',
            task_description='Create architecture with {specialist_name}',
            priority=1,
            estimated_hours=8
        )
        
        services['template'].add_task_to_phase(
            phase_id=phase_dev.id,
            task_key='implement',
            task_title='Implement Features for {phase_label}',
            task_description='Implement features',
            priority=1,
            estimated_hours=16
        )
        
        # Step 4: Publish template
        template = services['template'].publish_template(template.id)
        assert template.status == 'published'
        
        # Step 5: Instantiate
        instance = services['instance'].instantiate_workflow(
            template_id=template.id,
            instance_name="Product Launch #1",
            specialist_assignments={
                'planning': 'alice@example.com',
                'development': 'bob@example.com',
                'testing': 'carol@example.com'
            }
        )
        
        # Step 6: Verify instance created
        assert instance.id is not None
        assert instance.status == 'ready'
        
        # Step 7: Verify tasks generated
        tasks = repos['task'].get_instance_tasks(instance.id)
        assert len(tasks) == 3  # 1 planning + 1 dev + 0 testing (no task)
        
        # Step 8: Verify task assignments
        planning_tasks = [t for t in tasks if t.phase == 'planning']
        assert planning_tasks[0].assignee == 'alice@example.com'
        
        dev_tasks = [t for t in tasks if t.phase == 'development']
        assert dev_tasks[0].assignee == 'bob@example.com'
        
        # Step 9: Verify all tasks initially blocked
        assert all(t.status == 'blocked' for t in tasks)
        
        # Step 10: Verify placeholder resolution
        planning_task = planning_tasks[0]
        assert 'Architecture' in planning_task.title  # {phase_label} resolved
        assert 'Alice Johnson' in planning_task.description  # {specialist_name} resolved
    
    def test_error_scenario_missing_specialist(self, services, real_db, repos):
        """Instantiate with missing specialist → ValidationError"""
        # Create and publish template
        template = services['template'].create_template("Test Template")
        services['template'].add_phase(
            template_id=template.id,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='pm',
            phase_order=1
        )
        services['template'].publish_template(template.id)
        
        # Try to instantiate without creating specialist
        with pytest.raises(SpecialistNotFoundError):
            services['instance'].instantiate_workflow(
                template_id=template.id,
                instance_name="Test Instance",
                specialist_assignments={
                    'phase1': 'unknown@example.com'  # Specialist doesn't exist
                }
            )
    
    def test_error_scenario_circular_dependency(self, services, repos, real_db):
        """Task circular dependency → CircularDependencyError"""
        # Create template with tasks that form a cycle
        template = services['template'].create_template("Circular Test")
        phase = services['template'].add_phase(
            template_id=template.id,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='pm',
            phase_order=1
        )
        
        # Task A
        task_a = services['template'].add_task_to_phase(
            phase_id=phase.id,
            task_key='task_a',
            task_title='Task A',
            depends_on_key=None
        )
        
        # Task B depends on A
        task_b = services['template'].add_task_to_phase(
            phase_id=phase.id,
            task_key='task_b',
            task_title='Task B',
            depends_on_key='task_a'
        )
        
        # Task C depends on B
        task_c = services['template'].add_task_to_phase(
            phase_id=phase.id,
            task_key='task_c',
            task_title='Task C',
            depends_on_key='task_b'
        )
        
        # Try to create circular: Task A depends on C
        with pytest.raises(ValidationError):  # Should catch during add or publish
            services['template'].add_task_to_phase(
                phase_id=phase.id,
                task_key='task_a',
                task_title='Task A (updated)',
                depends_on_key='task_c'  # Creates cycle
            )
```

---

## 4. E2E テスト & BDD ステップ定義

### 4-1. BDD ステップ定義ファイル構成

```
tests/workflow/e2e/
├── __init__.py
├── conftest.py                          # Shared E2E fixtures
├── step_defs/
│   ├── __init__.py
│   ├── template_steps.py                # Template Given/When/Then
│   ├── instance_steps.py                # Instance Given/When/Then
│   └── task_steps.py                    # Task Given/When/Then
└── features/
    └── (symlink to /features/workflow-template.feature)
```

### 4-2. ステップ定義実装例

```python
# tests/workflow/e2e/step_defs/template_steps.py

import pytest
from pytest_bdd import given, when, then, parsers
from datetime import datetime

# ===== GIVEN STEPS =====

@given(parsers.parse('a workflow template named "{template_name}"'))
def workflow_template_named(template_svc, template_name):
    """Create template with given name"""
    template = template_svc.create_template(
        name=template_name,
        created_by="test@example.com"
    )
    return template

@given(parsers.parse('the template has description "{description}"'))
def template_has_description(workflow_template_named, template_svc, description):
    """Update template description"""
    # Note: In real implementation, may need to update DB directly
    # or modify service to support description update
    template = workflow_template_named
    template.description = description
    return template

@given(parsers.parse('the template defines the following phases:'))
def template_defines_phases(workflow_template_named, table):
    """Create phases from Gherkin table"""
    template = workflow_template_named
    template_svc = pytest.g.template_svc  # Access from context
    
    for row in table:
        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key=row['Phase Name'].lower().replace(' ', '_'),
            phase_label=row['Phase Name'],
            specialist_type=row['Specialist Type'].lower(),
            phase_order=int(row.get('phase_order', 1)),
            is_parallel=row['Sequential'].lower() == 'false'
        )
        # Store for reference in later steps
        if not hasattr(pytest.g, 'phases'):
            pytest.g.phases = {}
        pytest.g.phases[row['Phase Name']] = phase
    
    return template

# ===== WHEN STEPS =====

@when('I create the workflow template')
def create_workflow_template(workflow_template_named):
    """Trigger template creation (already done in Given)"""
    pytest.g.created_template = workflow_template_named
    return workflow_template_named

# ===== THEN STEPS =====

@then('the template should be stored with ID')
def template_stored_with_id(workflow_template_named):
    """Verify template has ID"""
    assert workflow_template_named.id is not None

@then(parsers.parse('the template should contain {phase_count} phases in order'))
def template_contains_phases(workflow_template_named, phase_count):
    """Verify phase count and order"""
    template_svc = pytest.g.template_svc
    phases = template_svc.template_repo.get_phases(workflow_template_named.id)
    
    assert len(phases) == int(phase_count)
    
    # Verify order
    for i, phase in enumerate(phases):
        assert phase.phase_order == i + 1

@then('each phase should have defined task templates')
def each_phase_has_tasks(workflow_template_named):
    """Verify each phase has at least one task"""
    template_svc = pytest.g.template_svc
    phases = template_svc.template_repo.get_phases(workflow_template_named.id)
    
    for phase in phases:
        tasks = template_svc.template_repo.get_tasks_for_phase(phase.id)
        assert len(tasks) > 0, f"Phase {phase.phase_label} has no tasks"
```

### 4-3. インスタンス化ステップ定義

```python
# tests/workflow/e2e/step_defs/instance_steps.py

from pytest_bdd import given, when, then, parsers

@given(parsers.parse('a stored workflow template "{template_name}"'))
def stored_template(template_svc, template_name):
    """Reference previously created template"""
    # Get from context or create
    if hasattr(pytest.g, 'templates') and template_name in pytest.g.templates:
        return pytest.g.templates[template_name]
    
    # Otherwise create new
    template = template_svc.create_template(template_name)
    return template

@given(parsers.parse('the template has {phase_count} phases with defined tasks'))
def template_with_phases(stored_template, template_svc, phase_count):
    """Verify template has specified phases"""
    phases = template_svc.template_repo.get_phases(stored_template.id)
    assert len(phases) == int(phase_count)

@given(parsers.parse('I have assigned specialists:'))
def assigned_specialists(table):
    """Store specialist assignments from table"""
    assignments = {}
    for row in table:
        phase_key = row['Phase Name'].lower().replace(' ', '_')
        assignments[phase_key] = row['Assigned Specialist']
    
    pytest.g.specialist_assignments = assignments
    return assignments

@when('I instantiate the template with specialist assignments')
def instantiate_template(stored_template, instance_svc):
    """Instantiate template"""
    instance = instance_svc.instantiate_workflow(
        template_id=stored_template.id,
        instance_name=f"{stored_template.name} Instance",
        specialist_assignments=pytest.g.specialist_assignments
    )
    
    pytest.g.created_instance = instance
    return instance

@then('a new workflow instance should be created')
def instance_created(instantiate_template):
    """Verify instance was created"""
    assert instantiate_template.id is not None
    assert instantiate_template.status == 'ready'

@then('the instance should reference the template')
def instance_references_template(instantiate_template, stored_template):
    """Verify instance points to template"""
    assert instantiate_template.template_id == stored_template.id

@then(parsers.parse('the instance should contain {phase_count} phase instances'))
def instance_has_phase_instances(instantiate_template, instance_repo, phase_count):
    """Verify phase instance count"""
    phases = instance_repo.get_phase_instances(instantiate_template.id)
    assert len(phases) == int(phase_count)

@then('each phase should be assigned to the specified specialist')
def phases_assigned_to_specialists(instantiate_template, instance_repo):
    """Verify specialist assignments"""
    assignments = instance_repo.get_instance_specialists(instantiate_template.id)
    
    for assignment in assignments:
        assert assignment.specialist_id is not None
        assert assignment.specialist_slug is not None
```

### 4-4. タスク生成ステップ定義

```python
# tests/workflow/e2e/step_defs/task_steps.py

from pytest_bdd import given, when, then, parsers

@given(parsers.parse('a workflow instance created from "{template_name}" template'))
def instance_from_template(template_svc, instance_svc, template_name):
    """Create instance from template"""
    # Create template
    template = template_svc.create_template(template_name)
    template_svc.publish_template(template.id)
    
    # Instantiate
    instance = instance_svc.instantiate_workflow(
        template_id=template.id,
        instance_name=f"{template_name} #1",
        specialist_assignments={...}
    )
    
    pytest.g.workflow_instance = instance
    return instance

@given(parsers.parse('the instance has {phase_count} phases with assigned specialists'))
def instance_has_phases_with_specialists(instance_from_template, phase_count):
    """Verify phases are assigned"""
    instance = instance_from_template
    assert instance.status == 'ready'

@when('I trigger auto-task generation')
def trigger_task_generation(instance_from_template, task_gen_svc):
    """Generate tasks (usually automatic, but allow explicit trigger)"""
    # Tasks should already be generated during instantiation
    pytest.g.task_generation_triggered = True

@then('tasks should be generated for each phase:')
def tasks_generated_for_phases(table, task_repo):
    """Verify tasks match expected count per phase"""
    instance = pytest.g.workflow_instance
    
    expected_by_phase = {}
    for row in table:
        phase_key = row['Phase Name'].lower().replace(' ', '_')
        expected_by_phase[phase_key] = {
            'count': int(row['Task Count']),
            'assignee': row['Assignee']
        }
    
    tasks = task_repo.get_instance_tasks(instance.id)
    
    for phase_key, expected in expected_by_phase.items():
        phase_tasks = [t for t in tasks if t.phase == phase_key]
        assert len(phase_tasks) == expected['count'], \
            f"Phase {phase_key}: expected {expected['count']}, got {len(phase_tasks)}"
        
        for task in phase_tasks:
            assert task.assignee == expected['assignee']

@then('each task should have title, description, and assignee')
def tasks_have_details(task_repo):
    """Verify task details"""
    instance = pytest.g.workflow_instance
    tasks = task_repo.get_instance_tasks(instance.id)
    
    for task in tasks:
        assert task.title is not None and len(task.title) > 0
        assert task.assignee is not None and '@' in task.assignee

@then('tasks should respect phase sequential order')
def tasks_respect_phase_order(task_repo, template_repo):
    """Verify inter-phase ordering constraints"""
    instance = pytest.g.workflow_instance
    tasks = task_repo.get_instance_tasks(instance.id)
    
    # All Phase N tasks should have dependencies to Phase N-1 tasks
    # (Implementation detail depends on data structure)

@then('phase tasks should only become active after previous phase completion')
def phase_tasks_blocked_until_predecessor(task_repo):
    """Verify initial task status is blocked"""
    instance = pytest.g.workflow_instance
    tasks = task_repo.get_instance_tasks(instance.id)
    
    # All tasks initially blocked
    assert all(t.status == 'blocked' for t in tasks)
```

---

## 5. テスト DB 環境セットアップ

### 5-1. テスト用 SQLite DB 初期化

```python
# tests/workflow/conftest.py (Root conftest)

import pytest
import sqlite3
import tempfile
from pathlib import Path

@pytest.fixture(scope='session')
def test_db_schema():
    """Test database schema initialization SQL"""
    return """
    CREATE TABLE IF NOT EXISTS workflow_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        status TEXT DEFAULT 'draft',
        created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME,
        CHECK (status IN ('draft', 'published', 'archived'))
    );
    
    CREATE TABLE IF NOT EXISTS wf_template_phases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        phase_key TEXT NOT NULL,
        phase_label TEXT NOT NULL,
        specialist_type TEXT NOT NULL,
        phase_order INTEGER NOT NULL,
        is_parallel BOOLEAN DEFAULT 0,
        task_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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
        estimated_hours FLOAT,
        task_order INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id),
        FOREIGN KEY (template_id) REFERENCES workflow_templates(id),
        UNIQUE (phase_id, task_key)
    );
    
    CREATE TABLE IF NOT EXISTS workflow_instances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        context TEXT,  -- JSON
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        started_at DATETIME,
        completed_at DATETIME,
        FOREIGN KEY (template_id) REFERENCES workflow_templates(id),
        CHECK (status IN ('pending', 'ready', 'running', 'completed'))
    );
    
    CREATE TABLE IF NOT EXISTS workflow_instance_specialists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id INTEGER NOT NULL,
        phase_id INTEGER NOT NULL,
        specialist_id INTEGER NOT NULL,
        specialist_slug TEXT NOT NULL,
        specialist_name TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (instance_id) REFERENCES workflow_instances(id),
        FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id),
        FOREIGN KEY (specialist_id) REFERENCES agents(id),
        UNIQUE (instance_id, phase_id)
    );
    
    CREATE TABLE IF NOT EXISTS wf_instance_nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id INTEGER NOT NULL,
        template_node_id INTEGER,
        node_key TEXT NOT NULL,
        node_type TEXT DEFAULT 'phase',
        status TEXT DEFAULT 'waiting',
        result TEXT,
        started_at DATETIME,
        completed_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (instance_id) REFERENCES workflow_instances(id),
        CHECK (status IN ('waiting', 'ready', 'running', 'completed'))
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
        estimated_hours FLOAT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        started_at DATETIME,
        completed_at DATETIME,
        unblocked_at DATETIME,
        FOREIGN KEY (workflow_instance_id) REFERENCES workflow_instances(id),
        CHECK (status IN ('blocked', 'pending', 'in_progress', 'completed'))
    );
    
    CREATE TABLE IF NOT EXISTS task_dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        predecessor_id INTEGER NOT NULL,
        successor_id INTEGER NOT NULL,
        dep_type TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (predecessor_id) REFERENCES dev_tasks(id),
        FOREIGN KEY (successor_id) REFERENCES dev_tasks(id),
        UNIQUE (predecessor_id, successor_id)
    );
    
    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        specialist_type TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """

@pytest.fixture
def temp_db(tmp_path, test_db_schema):
    """Create temporary test database with schema"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(test_db_schema)
    conn.commit()
    
    yield conn
    
    conn.close()
    db_path.unlink()

@pytest.fixture
def memory_db(test_db_schema):
    """Create in-memory test database (faster for unit tests)"""
    conn = sqlite3.connect(':memory:')
    conn.executescript(test_db_schema)
    conn.commit()
    
    yield conn
    
    conn.close()
```

### 5-2. テスト DB へのアクセス設定

```python
# tests/workflow/integration/conftest.py

import pytest
from workflow.repositories.template import TemplateRepository
from workflow.repositories.instance import InstanceRepository
from workflow.repositories.task import TaskRepository
from workflow.repositories.specialist import SpecialistRepository

@pytest.fixture
def db_connection(temp_db):
    """Provide DB connection for integration tests"""
    return temp_db

@pytest.fixture
def repositories(db_connection):
    """Initialize all repositories with test DB"""
    return {
        'template': TemplateRepository(db_connection),
        'instance': InstanceRepository(db_connection),
        'task': TaskRepository(db_connection),
        'specialist': SpecialistRepository(db_connection),
    }
```

---

## 6. テスト実行パイプライン

### 6-1. pytest 設定 (pytest.ini)

```ini
[pytest]
# tests/pytest.ini

# Test discovery
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Output
addopts =
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=workflow
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=70

# Markers
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow tests
    db: Database tests

# Test paths
testpaths = tests

# Timeout
timeout = 30
timeout_method = thread

# BDD
bdd_features_base_dir = features
```

### 6-2. テスト実行スクリプト

```bash
#!/bin/bash
# scripts/run_tests.sh

set -e

echo "Running Workflow Template System Tests"
echo "======================================"

# Unit tests
echo ""
echo "1. Running unit tests..."
pytest tests/workflow/unit -m unit -v

# Integration tests
echo ""
echo "2. Running integration tests..."
pytest tests/workflow/integration -m integration -v

# E2E / BDD tests
echo ""
echo "3. Running E2E/BDD tests..."
pytest tests/workflow/e2e -m e2e -v

# Coverage report
echo ""
echo "4. Coverage summary:"
pytest --cov=workflow --cov-report=term-missing

echo ""
echo "All tests passed!"
```

### 6-3. GitHub Actions (CI/CD)

```yaml
# .github/workflows/test.yml

name: Workflow Template Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-test.txt
    
    - name: Run unit tests
      run: pytest tests/workflow/unit -m unit -v
    
    - name: Run integration tests
      run: pytest tests/workflow/integration -m integration -v
    
    - name: Run E2E tests
      run: pytest tests/workflow/e2e -m e2e -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml
```

---

## 7. カバレッジ目標

### 7-1. カバレッジ基準

| コンポーネント | 目標 | 説明 |
|-----------|------|------|
| **Services** | >85% | Core business logic |
| **Repositories** | >80% | Data access layer |
| **Validators** | >90% | Validation logic (critical) |
| **Models** | >70% | Data models (mostly passthrough) |
| **Exceptions** | >80% | Error handling |
| **全体** | >75% | Overall coverage |

### 7-2. カバレッジレポート生成

```bash
# Generate HTML coverage report
pytest --cov=workflow --cov-report=html

# Open report
open htmlcov/index.html
```

### 7-3. カバレッジチェック (CI)

```bash
# Fail if coverage < 75%
pytest --cov=workflow --cov-fail-under=75
```

---

## 8. テスト実行順序と依存関係

### 8-1. 推奨実行順序

```
1. ユニットテスト (Unit Tests)
   └─ 依存なし、高速、>80% coverage

2. 統合テスト (Integration Tests)
   └─ ユニットテスト成功後、真正 DB 使用

3. E2E テスト (E2E/BDD Tests)
   └─ 統合テスト成功後、エンドツーエンドフロー検証
```

### 8-2. テスト実行時間目安

| テストタイプ | 目安 | 並列実行 |
|-----------|------|--------|
| Unit | <5秒 | ✅ 可能 |
| Integration | 10-20秒 | ❌ 不可（DB ロック） |
| E2E | 30-60秒 | ❌ 不可 |
| **Total** | **1-2分** | — |

---

## 9. テスト実装チェックリスト

### 9-1. ユニットテスト実装タスク

- [ ] TemplateService テスト（8 テスト）
  - [ ] create_template
  - [ ] add_phase
  - [ ] add_task_to_phase
  - [ ] publish_template
- [ ] TemplateValidator テスト（5 テスト）
- [ ] InstanceService テスト（5 テスト）
- [ ] TaskGenerationService テスト（6 テスト）
- [ ] SpecialistAssignmentService テスト（4 テスト）

**小計: 28 ユニットテスト**

### 9-2. 統合テスト実装タスク

- [ ] Template ライフサイクル（1 テスト）
- [ ] Full instantiation workflow（1 テスト）
- [ ] Task generation with dependencies（1 テスト）
- [ ] Error scenarios（3 テスト）

**小計: 6 統合テスト**

### 9-3. E2E/BDD テスト実装タスク

- [ ] workflow-template.feature Scenario 1: Create template
- [ ] workflow-template.feature Scenario 2: Instantiate instance
- [ ] workflow-template.feature Scenario 3: Auto-generate tasks

**小計: 3 E2E テスト**

---

## まとめ

Phase 5 テストコード設計により、以下の実装準備が整いました：

✅ **テストフレームワーク選定** - pytest + pytest-bdd  
✅ **3層テスト戦略** - Unit / Integration / E2E  
✅ **テスト DB セットアップ** - SQLite in-memory & temp file  
✅ **テスト実行パイプライン** - CI/CD 対応  
✅ **カバレッジ基準** - 全体 >75%, Services >85%  

**次フェーズ（Phase 6）では、これらのテストコードを実装します。**

---

## 参考資料

- **詳細インターフェース**: `/docs/phase4-detailed-interface-design.md`
- **BDD シナリオ**: `/features/workflow-template.feature`
- **流れ図**: `/docs/flow-design.md`
