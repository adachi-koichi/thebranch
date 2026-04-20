"""UAT test fixtures for workflow integration and delegation chain tests"""

import pytest
from unittest.mock import MagicMock, Mock
from datetime import datetime
import json


@pytest.fixture
def mock_orchestrator():
    """Mock Orchestrator service"""
    orch = MagicMock()
    orch.id = "orchestrator-1"
    orch.role = "orchestrator"
    orch.delegate_to_em = MagicMock(return_value={"status": "delegated", "em_id": "em-1"})
    return orch


@pytest.fixture
def mock_engineering_manager():
    """Mock Engineering Manager service"""
    em = MagicMock()
    em.id = "em-1"
    em.role = "engineering_manager"
    em.delegate_to_engineer = MagicMock(return_value={"status": "delegated", "engineer_id": "eng-1"})
    em.get_task_status = MagicMock(return_value={"task_id": "task-1", "status": "in_progress"})
    return em


@pytest.fixture
def mock_engineer():
    """Mock Engineer service"""
    eng = MagicMock()
    eng.id = "eng-1"
    eng.role = "engineer"
    eng.execute_task = MagicMock(return_value={"status": "completed", "result": "success"})
    eng.get_task_status = MagicMock(return_value={"task_id": "task-1", "status": "completed"})
    return eng


@pytest.fixture
def delegation_chain_log():
    """Track delegation chain execution"""
    return {
        "delegations": [],
        "timestamps": {},
        "errors": [],
    }


@pytest.fixture
def workflow_instance():
    """Sample workflow instance for UAT"""
    return {
        "id": "workflow-001",
        "name": "QA Release Process",
        "status": "active",
        "phases": [
            {
                "id": "phase-1",
                "name": "Requirements",
                "specialist_type": "product_manager",
                "assigned_to": "pm@company.com",
                "status": "active",
                "task_count": 2,
                "completed_tasks": 0,
                "sequential": True,
            },
            {
                "id": "phase-2",
                "name": "Implementation",
                "specialist_type": "engineer",
                "assigned_to": "eng@company.com",
                "status": "locked",
                "task_count": 3,
                "completed_tasks": 0,
                "sequential": True,
            },
            {
                "id": "phase-3",
                "name": "Testing",
                "specialist_type": "qa_engineer",
                "assigned_to": "qa@company.com",
                "status": "locked",
                "task_count": 2,
                "completed_tasks": 0,
                "sequential": False,
            },
        ],
        "tasks": [
            {"id": "task-1", "phase_id": "phase-1", "title": "Gather Requirements", "status": "pending"},
            {"id": "task-2", "phase_id": "phase-1", "title": "Review Spec", "status": "pending"},
            {"id": "task-3", "phase_id": "phase-2", "title": "Implement Feature", "status": "blocked"},
            {"id": "task-4", "phase_id": "phase-2", "title": "Code Review", "status": "blocked"},
            {"id": "task-5", "phase_id": "phase-2", "title": "Unit Tests", "status": "blocked"},
            {"id": "task-6", "phase_id": "phase-3", "title": "Integration Tests", "status": "blocked"},
            {"id": "task-7", "phase_id": "phase-3", "title": "UAT Verification", "status": "blocked"},
        ],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def error_scenarios():
    """Error scenarios for error handling tests"""
    return [
        {
            "name": "task_validation_failure",
            "error_type": "ValidationError",
            "message": "Task validation failed: missing required fields",
            "recoverable": True,
        },
        {
            "name": "phase_transition_blocked",
            "error_type": "PhaseTransitionError",
            "message": "Cannot transition phase: not all tasks completed",
            "recoverable": True,
        },
        {
            "name": "specialist_unavailable",
            "error_type": "SpecialistError",
            "message": "Assigned specialist is unavailable",
            "recoverable": True,
        },
        {
            "name": "database_connection_error",
            "error_type": "DatabaseError",
            "message": "Failed to connect to database",
            "recoverable": False,
        },
    ]


@pytest.fixture
def audit_log():
    """Track audit log entries"""
    return {
        "entries": [],
        "errors": [],
        "state_changes": [],
        "add_entry": lambda entry: audit_log["entries"].append({**entry, "timestamp": datetime.now().isoformat()}),
    }


@pytest.fixture
def api_client():
    """Mock HTTP client for API endpoint testing"""
    client = MagicMock()
    client.post = MagicMock()
    client.get = MagicMock()
    client.patch = MagicMock()
    client.delete = MagicMock()
    return client
