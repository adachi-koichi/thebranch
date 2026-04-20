"""Integration test fixtures with real database"""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock

from workflow.services.template import TemplateService
from workflow.services.instance import WorkflowInstanceService
from workflow.services.task_gen import TaskGenerationService
from workflow.services.assignment import SpecialistAssignmentService
from workflow.repositories.template import TemplateRepository
from workflow.repositories.instance import InstanceRepository
from workflow.repositories.task import TaskRepository
from workflow.repositories.specialist import SpecialistRepository
from workflow.validation.template import TemplateValidator
from workflow.validation.instance import InstanceValidator
from workflow.validation.task import TaskValidator
from workflow.validation.assignment import AssignmentValidator


@pytest.fixture
def test_db_schema():
    """テストデータベーススキーマ"""
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
        context TEXT,
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
        UNIQUE (instance_id, phase_id)
    );

    CREATE TABLE IF NOT EXISTS wf_instance_nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id INTEGER NOT NULL,
        phase_id INTEGER NOT NULL,
        phase_key TEXT NOT NULL,
        status TEXT DEFAULT 'waiting',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (instance_id) REFERENCES workflow_instances(id),
        FOREIGN KEY (phase_id) REFERENCES wf_template_phases(id),
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
def real_db(tmp_path, test_db_schema):
    """Create real SQLite test database with schema"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(test_db_schema)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def memory_db(test_db_schema):
    """メモリ内SQLiteテストデータベース"""
    conn = sqlite3.connect(':memory:')
    conn.executescript(test_db_schema)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def repos(tmp_path, test_db_schema):
    """Repository層の統合fixture（ファイルベースDB接続を共有）"""
    db_path = str(tmp_path / "test.db")

    # スキーマを初期化
    conn = sqlite3.connect(db_path)
    conn.executescript(test_db_schema)
    conn.commit()
    conn.close()

    # 同じdb_pathを指すリポジトリを作成
    template_repo = TemplateRepository(db_path)
    instance_repo = InstanceRepository(db_path)
    task_repo = TaskRepository(db_path)
    specialist_repo = SpecialistRepository(db_path)

    return {
        'template': template_repo,
        'instance': instance_repo,
        'task': task_repo,
        'specialist': specialist_repo
    }


@pytest.fixture
def services(repos):
    """Service層の統合fixture（repos を利用）"""
    template_validator = TemplateValidator(repos['template'])
    template_svc = TemplateService(repos['template'], template_validator)

    assignment_validator = AssignmentValidator()
    assignment_svc = SpecialistAssignmentService(repos['specialist'], assignment_validator)

    task_validator = TaskValidator(repos['task'])
    task_gen_svc = TaskGenerationService(
        repos['task'],
        repos['template'],
        repos['instance'],
        task_validator
    )

    instance_validator = InstanceValidator(repos['instance'], repos['template'])
    instance_svc = WorkflowInstanceService(
        repos['instance'],
        repos['template'],
        task_gen_svc,
        assignment_svc,
        instance_validator
    )

    return {
        'template': template_svc,
        'instance': instance_svc,
        'task_gen': task_gen_svc,
        'assignment': assignment_svc
    }


@pytest.fixture
def created_agents(repos):
    """事前作成されたエージェント（alice, bob, carol, dave）"""
    specialist_repo = repos['specialist']

    agents = {
        'alice': specialist_repo.create_agent('alice', 'alice@example.com', 'pm'),
        'bob': specialist_repo.create_agent('bob', 'bob@example.com', 'engineer'),
        'carol': specialist_repo.create_agent('carol', 'carol@example.com', 'qa'),
        'dave': specialist_repo.create_agent('dave', 'dave@example.com', 'designer')
    }

    return agents
