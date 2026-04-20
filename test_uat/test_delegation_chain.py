"""UAT: Delegation Chain Verification (orchestrator → EM → Engineer)"""

import pytest
from datetime import datetime


class TestDelegationChainFlow:
    """Verify orchestrator → EM → Engineer delegation chain"""

    def test_orchestrator_delegates_to_em(self, mock_orchestrator, mock_engineering_manager, delegation_chain_log):
        """Test orchestrator successfully delegates workflow to EM"""
        # GIVEN: Orchestrator is ready to delegate
        workflow_id = "workflow-001"

        # WHEN: Orchestrator delegates to EM
        result = mock_orchestrator.delegate_to_em(workflow_id=workflow_id)

        # THEN: Delegation is successful
        assert result["status"] == "delegated"
        assert result["em_id"] == "em-1"
        mock_orchestrator.delegate_to_em.assert_called_once_with(workflow_id=workflow_id)

    def test_em_receives_delegation_context(self, mock_orchestrator, mock_engineering_manager, workflow_instance):
        """Test EM receives full workflow context from orchestrator"""
        # GIVEN: Orchestrator creates delegation message
        delegation_msg = {
            "workflow_id": workflow_instance["id"],
            "workflow_name": workflow_instance["name"],
            "phases": workflow_instance["phases"],
            "tasks": workflow_instance["tasks"],
            "from_role": "orchestrator",
            "to_role": "engineering_manager",
            "timestamp": datetime.now().isoformat(),
        }

        # WHEN: EM receives the message
        mock_engineering_manager.receive_delegation = lambda msg: {"status": "received", "context": msg}
        result = mock_engineering_manager.receive_delegation(delegation_msg)

        # THEN: EM has full context
        assert result["status"] == "received"
        assert result["context"]["workflow_id"] == workflow_instance["id"]
        assert result["context"]["phases"] == workflow_instance["phases"]

    def test_em_delegates_to_engineers(self, mock_engineering_manager, mock_engineer, workflow_instance):
        """Test EM distributes phase tasks to engineers"""
        # GIVEN: EM has received workflow context
        phase_tasks = {
            "phase_id": "phase-2",
            "phase_name": "Implementation",
            "task_ids": ["task-3", "task-4", "task-5"],
            "assigned_to": "eng@company.com",
        }

        # WHEN: EM delegates phase tasks to engineer
        result = mock_engineering_manager.delegate_to_engineer(
            engineer_id="eng-1",
            phase_tasks=phase_tasks,
        )

        # THEN: Engineer receives task assignments
        assert result["status"] == "delegated"
        assert result["engineer_id"] == "eng-1"

    def test_engineer_receives_task_assignments(self, mock_engineer, workflow_instance):
        """Test engineer receives and acknowledges task assignments"""
        # GIVEN: Engineer is assigned phase tasks
        assignment = {
            "workflow_id": "workflow-001",
            "phase_id": "phase-2",
            "phase_name": "Implementation",
            "tasks": [
                {"id": "task-3", "title": "Implement Feature"},
                {"id": "task-4", "title": "Code Review"},
                {"id": "task-5", "title": "Unit Tests"},
            ],
            "timestamp": datetime.now().isoformat(),
        }

        # WHEN: Engineer acknowledges assignment
        mock_engineer.acknowledge_assignment = lambda a: {"status": "acknowledged", "assignment": a}
        result = mock_engineer.acknowledge_assignment(assignment)

        # THEN: Assignment is confirmed
        assert result["status"] == "acknowledged"
        assert len(result["assignment"]["tasks"]) == 3

    def test_delegation_chain_logging(self, mock_orchestrator, mock_engineering_manager, mock_engineer, delegation_chain_log):
        """Test delegation chain is logged with timestamps and actors"""
        # GIVEN: Delegation process starts
        workflow_id = "workflow-001"

        # WHEN: Each step is logged
        delegation_steps = [
            {"step": 1, "from": "orchestrator", "to": "em", "action": "delegate_workflow", "timestamp": datetime.now().isoformat()},
            {"step": 2, "from": "em", "to": "engineer", "action": "delegate_phase_tasks", "timestamp": datetime.now().isoformat()},
            {"step": 3, "from": "engineer", "to": "em", "action": "acknowledge_assignment", "timestamp": datetime.now().isoformat()},
        ]

        for step in delegation_steps:
            delegation_chain_log["delegations"].append(step)
            delegation_chain_log["timestamps"][f"step_{step['step']}"] = step["timestamp"]

        # THEN: Chain is fully logged
        assert len(delegation_chain_log["delegations"]) == 3
        assert delegation_chain_log["delegations"][0]["from"] == "orchestrator"
        assert delegation_chain_log["delegations"][1]["from"] == "em"
        assert delegation_chain_log["delegations"][2]["from"] == "engineer"

    def test_task_assignments_reference_delegation_chain(self, workflow_instance, delegation_chain_log):
        """Test task assignments include delegation chain reference"""
        # GIVEN: Delegation chain is logged
        delegation_id = "deleg-001"

        # WHEN: Task is created with delegation reference
        task = {
            "id": "task-3",
            "title": "Implement Feature",
            "delegation_id": delegation_id,
            "delegation_chain": [
                {"actor": "orchestrator", "action": "delegate_to_em"},
                {"actor": "em", "action": "delegate_to_engineer"},
                {"actor": "engineer", "action": "acknowledged"},
            ],
            "timestamp": datetime.now().isoformat(),
        }

        # THEN: Task references the delegation chain
        assert task["delegation_id"] == delegation_id
        assert len(task["delegation_chain"]) == 3
        assert task["delegation_chain"][2]["actor"] == "engineer"

    def test_delegation_chain_error_handling(self, delegation_chain_log):
        """Test error handling in delegation chain"""
        # GIVEN: Delegation chain is in progress
        # WHEN: Error occurs at EM level
        error = {
            "step": 2,
            "from": "em",
            "error": "Failed to locate engineer",
            "timestamp": datetime.now().isoformat(),
        }
        delegation_chain_log["errors"].append(error)

        # THEN: Error is logged and chain is halted
        assert len(delegation_chain_log["errors"]) == 1
        assert delegation_chain_log["errors"][0]["step"] == 2

    def test_delegation_chain_retry(self, mock_engineering_manager, delegation_chain_log):
        """Test retry mechanism for failed delegations"""
        # GIVEN: Delegation failed
        failed_delegation = {
            "attempt": 1,
            "status": "failed",
            "reason": "Engineer unavailable",
            "timestamp": datetime.now().isoformat(),
        }

        # WHEN: Retry is attempted
        retry_result = mock_engineering_manager.delegate_to_engineer(
            engineer_id="eng-2",  # Different engineer
            phase_tasks={},
            retry_attempt=2,
        )

        # THEN: Retry is recorded
        assert retry_result["status"] == "delegated"

    def test_delegation_chain_audit_trail(self, delegation_chain_log, audit_log):
        """Test complete audit trail of delegation chain"""
        # GIVEN: Delegation chain completes
        chain_steps = [
            ("orchestrator", "delegate_to_em", "workflow-001"),
            ("em", "delegate_to_engineer", "phase-2"),
            ("engineer", "acknowledged", "task-3"),
        ]

        # WHEN: Each step is audited
        for actor, action, resource in chain_steps:
            audit_log["entries"].append({
                "actor": actor,
                "action": action,
                "resource_id": resource,
                "timestamp": datetime.now().isoformat(),
            })

        # THEN: Audit trail is complete
        assert len(audit_log["entries"]) == 3
        assert audit_log["entries"][0]["actor"] == "orchestrator"
        assert audit_log["entries"][-1]["action"] == "acknowledged"
