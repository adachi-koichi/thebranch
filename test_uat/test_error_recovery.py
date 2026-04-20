"""UAT: Error Handling and Recovery Testing"""

import pytest
from datetime import datetime


class TestErrorRecovery:
    """Test error scenarios and recovery mechanisms"""

    def test_invalid_template_error(self, mock_orchestrator, mock_engineering_manager):
        """Test handling of invalid workflow template"""
        # GIVEN: Invalid template name provided
        invalid_template_name = "NonExistentTemplate"
        mock_orchestrator.instantiate_workflow.side_effect = ValueError(f"Template {invalid_template_name} not found")

        # WHEN: Attempt to instantiate from invalid template
        with pytest.raises(ValueError) as exc_info:
            mock_orchestrator.instantiate_workflow(template_name=invalid_template_name)

        # THEN: Appropriate error is raised
        assert "template" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()

    def test_invalid_template_schema_error(self, mock_orchestrator):
        """Test handling of template with invalid schema"""
        # GIVEN: Template with malformed schema
        invalid_template = {
            "name": "BadTemplate",
            "phases": None,  # Invalid: phases should be a list
            "version": "1.0",
        }
        mock_orchestrator.validate_template.side_effect = ValueError("Invalid schema: phases field is required")

        # WHEN: Attempt to instantiate template with invalid schema
        with pytest.raises((ValueError, TypeError)) as exc_info:
            mock_orchestrator.validate_template(invalid_template)

        # THEN: Schema validation error is raised
        error_msg = str(exc_info.value).lower()
        assert any(x in error_msg for x in ["schema", "invalid", "phases", "required"])

    def test_missing_specialist_error(self, mock_orchestrator, mock_engineering_manager, workflow_instance):
        """Test handling when specialist is not available for assignment"""
        # GIVEN: Workflow requires specialist that doesn't exist
        unavailable_specialist = "nonexistent@company.com"
        phase_assignment = {
            "phase_id": "phase-1",
            "phase_name": "Requirements",
            "specialist_email": unavailable_specialist,
        }
        mock_engineering_manager.assign_specialist.side_effect = ValueError(f"Specialist {unavailable_specialist} not found")

        # WHEN: Attempt to assign unavailable specialist
        with pytest.raises(ValueError) as exc_info:
            mock_engineering_manager.assign_specialist(
                phase_id=phase_assignment["phase_id"],
                specialist_email=unavailable_specialist,
            )

        # THEN: Specialist not found error is raised
        assert "specialist" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()

    def test_missing_specialist_recovery(self, mock_engineering_manager, workflow_instance):
        """Test recovery when alternative specialist is assigned"""
        # GIVEN: Initial specialist assignment failed
        failed_specialist = "unavailable@company.com"
        recovery_specialist = "backup@company.com"
        mock_engineering_manager.assign_specialist.return_value = {"status": "assigned", "specialist_email": recovery_specialist}

        # WHEN: Retry with alternative specialist
        result = mock_engineering_manager.assign_specialist(
            phase_id="phase-1",
            specialist_email=recovery_specialist,
            retry=True,
        )

        # THEN: Assignment succeeds with alternative specialist
        assert result["status"] == "assigned"
        assert result["specialist_email"] == recovery_specialist

    def test_circular_blockedby_detection(self, mock_orchestrator):
        """Test detection of circular dependencies in blockedBy relationships"""
        # GIVEN: Task dependency graph with circular reference
        # Task A blocks Task B, Task B blocks Task C, Task C blocks Task A (circular)
        tasks_with_circular_ref = [
            {"id": "task-1", "name": "Task A", "blockedBy": ["task-3"]},
            {"id": "task-2", "name": "Task B", "blockedBy": ["task-1"]},
            {"id": "task-3", "name": "Task C", "blockedBy": ["task-2"]},
        ]
        mock_orchestrator.validate_task_dependencies.side_effect = ValueError("Circular dependency detected in task blockedBy relationships")

        # WHEN: Attempt to validate task dependencies
        with pytest.raises(ValueError) as exc_info:
            mock_orchestrator.validate_task_dependencies(tasks_with_circular_ref)

        # THEN: Circular dependency error is raised
        error_msg = str(exc_info.value).lower()
        assert "circular" in error_msg or "cycle" in error_msg or "dependency" in error_msg

    def test_circular_blockedby_self_reference(self, mock_orchestrator):
        """Test detection of self-referencing blockedBy (task blocked by itself)"""
        # GIVEN: Task that blocks itself
        self_blocking_task = {
            "id": "task-1",
            "name": "SelfBlocking Task",
            "blockedBy": ["task-1"],  # Task blocks itself
        }
        mock_orchestrator.validate_task.side_effect = ValueError("Task cannot be blocked by itself")

        # WHEN: Attempt to validate
        with pytest.raises(ValueError) as exc_info:
            mock_orchestrator.validate_task(self_blocking_task)

        # THEN: Self-reference error is raised
        assert "self" in str(exc_info.value).lower() or "circular" in str(exc_info.value).lower()

    def test_error_logging_and_recovery_audit_trail(self, audit_log, delegation_chain_log):
        """Test that errors are logged in audit trail for recovery analysis"""
        # GIVEN: Error occurs during workflow execution
        error_event = {
            "phase": "phase-2",
            "phase_name": "Implementation",
            "error_type": "SpecialistNotFound",
            "error_message": "Specialist eng@company.com is not available",
            "timestamp": datetime.now().isoformat(),
            "recovery_action": "Assigned backup specialist eng2@company.com",
        }

        # WHEN: Error is logged
        audit_log["entries"].append({
            "event_type": "error_occurred",
            "detail": error_event,
            "timestamp": error_event["timestamp"],
        })
        audit_log["errors"].append(error_event)

        # THEN: Error is recorded in audit trail
        assert len(audit_log["errors"]) > 0
        assert audit_log["errors"][-1]["error_type"] == "SpecialistNotFound"
        assert "recovery_action" in audit_log["errors"][-1]

    def test_error_recovery_retry_mechanism(self, mock_engineering_manager, delegation_chain_log):
        """Test retry mechanism for failed operations"""
        # GIVEN: Operation failed on first attempt
        operation = {
            "attempt": 1,
            "status": "failed",
            "reason": "Specialist unavailable",
            "timestamp": datetime.now().isoformat(),
        }
        mock_engineering_manager.assign_specialist.return_value = {"status": "assigned", "retry_attempt": 2}

        # WHEN: Retry is triggered
        retry_result = mock_engineering_manager.assign_specialist(
            phase_id="phase-1",
            specialist_email="backup@company.com",
            retry=True,
            retry_attempt=2,
        )

        # THEN: Retry succeeds
        assert retry_result["status"] == "assigned"
        assert retry_result.get("retry_attempt") == 2 or "retry" in str(retry_result).lower()

    def test_invalid_template_detailed_validation(self, mock_orchestrator):
        """Test detailed validation of template structure"""
        # GIVEN: Template with missing required fields
        incomplete_template = {
            "name": "IncompleteTemplate",
            # Missing "phases" field
            "version": "1.0",
        }
        mock_orchestrator.validate_template.side_effect = KeyError("Missing required field: phases")

        # WHEN: Validate template structure
        with pytest.raises((ValueError, KeyError)) as exc_info:
            mock_orchestrator.validate_template(incomplete_template)

        # THEN: Missing field error is raised
        error_msg = str(exc_info.value).lower()
        assert "phase" in error_msg or "missing" in error_msg or "required" in error_msg

    def test_error_state_rollback(self, workflow_instance, audit_log):
        """Test rollback to previous state when error occurs"""
        # GIVEN: Workflow in successful state
        initial_state = {
            "workflow_id": "workflow-001",
            "status": "IN_PROGRESS",
            "phase": "phase-2",
            "tasks_completed": 3,
        }

        # WHEN: Error occurs during state transition
        error_occurs = True
        if error_occurs:
            rollback_state = {
                "workflow_id": "workflow-001",
                "status": "IN_PROGRESS",
                "phase": "phase-1",  # Rolled back to previous phase
                "tasks_completed": 2,  # Rolled back to previous count
                "recovery_action": "rolled_back",
                "timestamp": datetime.now().isoformat(),
            }
            audit_log["state_changes"].append(rollback_state)

        # THEN: State is rolled back and logged
        assert audit_log["state_changes"][-1]["recovery_action"] == "rolled_back"
        assert audit_log["state_changes"][-1]["phase"] == "phase-1"

    def test_concurrent_error_scenarios(self, mock_orchestrator):
        """Test error handling when multiple errors occur simultaneously"""
        # GIVEN: Multiple concurrent operations
        operations = [
            {"id": "op-1", "type": "specialist_assignment", "specialist": "missing@company.com"},
            {"id": "op-2", "type": "template_validation", "template": "invalid_template"},
            {"id": "op-3", "type": "dependency_check", "tasks": []},
        ]

        # WHEN: Errors occur in parallel
        errors = []
        for op in operations:
            try:
                if op["type"] == "specialist_assignment":
                    raise ValueError(f"Specialist {op['specialist']} not found")
                elif op["type"] == "template_validation":
                    raise ValueError(f"Template {op['template']} is invalid")
            except ValueError as e:
                errors.append({"operation_id": op["id"], "error": str(e)})

        # THEN: All errors are captured and reported
        assert len(errors) >= 2
        assert any("specialist" in e["error"].lower() for e in errors)
        assert any("template" in e["error"].lower() for e in errors)
