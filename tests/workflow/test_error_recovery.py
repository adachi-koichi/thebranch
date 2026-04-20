"""
tests/workflow/test_error_recovery.py — Workflow error recovery scenarios

Tests for:
1. Invalid Template: テンプレート名が存在しない、スキーマが不正
2. Missing Specialist: 割り当て対象の specialist がシステムに存在しない
3. Circular blockedBy: タスク依存関係に循環参照がある (A→B→C→A)
"""

import pytest
from unittest.mock import MagicMock

from workflow.exceptions import (
    ValidationError,
    CircularDependencyError,
)
from workflow.models import Phase, TaskDef
from workflow.validation.assignment import AssignmentValidator


# ---------------------------------------------------------------------------
# テスト: Scenario 1 - Invalid Template
# ---------------------------------------------------------------------------

class TestInvalidTemplate:
    """テンプレート不正エラーのリカバリーテスト"""

    def test_template_invalid_schema_missing_phases(
        self, template_validator, mock_template_repo
    ):
        """フェーズのないテンプレートは不正スキーマとしてエラーになること"""
        mock_template_repo.get_phases.return_value = []

        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_template_complete(template_id=1)
        assert 'no phases' in str(exc_info.value)

    def test_template_invalid_schema_empty_phase(
        self, template_validator, mock_template_repo
    ):
        """タスクのないフェーズはスキーマ不正としてエラーになること"""
        phase = Phase(
            id=1,
            template_id=1,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='engineer',
            phase_order=1,
        )
        mock_template_repo.get_phases.return_value = [phase]
        mock_template_repo.get_tasks_for_phase.return_value = []

        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_template_complete(template_id=1)
        assert 'no tasks' in str(exc_info.value)

    def test_template_invalid_schema_invalid_specialist_type(
        self, template_validator
    ):
        """不正なspecialist_typeはスキーマ不正としてエラーになること"""
        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_phase(
                template_id=1,
                phase_key='phase1',
                specialist_type='invalid_specialist_type',
                phase_order=1,
            )
        assert 'Invalid specialist_type' in str(exc_info.value)

    def test_template_invalid_phase_order(self, template_validator, mock_template_repo):
        """フェーズオーダーが不正（0以下）はスキーマ不正としてエラーになること"""
        mock_template_repo.get_phases.return_value = []

        with pytest.raises(ValidationError) as exc_info:
            template_validator.validate_phase(
                template_id=1,
                phase_key='phase1',
                specialist_type='engineer',
                phase_order=0,
            )
        assert 'phase_order must be >= 1' in str(exc_info.value)

    def test_template_recovery_with_valid_schema(
        self, template_validator, mock_template_repo
    ):
        """スキーマを修正すると正常に検証されること"""
        # Invalid state
        mock_template_repo.get_phases.return_value = []
        with pytest.raises(ValidationError):
            template_validator.validate_template_complete(template_id=1)

        # Recovery: Valid schema
        phase = Phase(
            id=1,
            template_id=1,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='engineer',
            phase_order=1,
        )
        task = TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key='task1',
            task_title='Task 1',
        )
        mock_template_repo.get_phases.return_value = [phase]
        mock_template_repo.get_tasks_for_phase.return_value = [task]

        # Should not raise after recovery
        template_validator.validate_template_complete(template_id=1)


# ---------------------------------------------------------------------------
# テスト: Scenario 2 - Missing Specialist (Assignment Validation)
# ---------------------------------------------------------------------------

class TestMissingSpecialist:
    """Specialist不在・割り当て不正のリカバリーテスト"""

    def test_missing_phase_assignment_raises_error(self):
        """割り当てのないフェーズはエラーになること"""
        validator = AssignmentValidator()

        phase1 = Phase(
            id=1,
            template_id=1,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1,
        )
        phase2 = Phase(
            id=2,
            template_id=1,
            phase_key='development',
            phase_label='Development',
            specialist_type='engineer',
            phase_order=2,
        )
        phases = [phase1, phase2]

        # planning のみ割り当てて development を割り当てない
        assignments = {'planning': 'pm@example.com'}

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_all_phases_assigned(phases, assignments)
        assert 'Missing assignments' in str(exc_info.value)

    def test_invalid_agent_name_raises_error(self):
        """空のエージェント名はエラーになること"""
        validator = AssignmentValidator()

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_agent(
                name='',
                email='engineer@example.com',
                specialist_type='engineer',
            )
        assert 'Invalid agent name' in str(exc_info.value)

    def test_invalid_email_raises_error(self):
        """不正なメールアドレスはエラーになること"""
        validator = AssignmentValidator()

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_agent(
                name='Test Engineer',
                email='invalid_email',
                specialist_type='engineer',
            )
        assert 'Invalid email' in str(exc_info.value)

    def test_invalid_specialist_type_raises_error(self):
        """不正なspecialist_typeはエラーになること"""
        validator = AssignmentValidator()

        with pytest.raises(ValidationError) as exc_info:
            validator.validate_agent(
                name='Test',
                email='test@example.com',
                specialist_type='invalid_type',
            )
        assert 'Invalid specialist_type' in str(exc_info.value)

    def test_specialist_type_match_detection(self):
        """specialist typeのマッチ判定ができること"""
        validator = AssignmentValidator()

        # Match
        match = validator.validate_specialist_type_match(
            specialist_type='engineer',
            required_type='engineer',
        )
        assert match is True

        # Mismatch
        mismatch = validator.validate_specialist_type_match(
            specialist_type='engineer',
            required_type='qa',
        )
        assert mismatch is False

    def test_specialist_recovery_with_valid_assignment(self):
        """有効な割り当てに修正すると検証が通ること"""
        validator = AssignmentValidator()

        phase1 = Phase(
            id=1,
            template_id=1,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1,
        )
        phases = [phase1]

        # Invalid: missing assignment
        with pytest.raises(ValidationError):
            validator.validate_all_phases_assigned(phases, {})

        # Recovery: add assignment
        assignments = {'planning': 'pm@example.com'}

        # Should not raise after recovery
        validator.validate_all_phases_assigned(phases, assignments)

    def test_agent_validation_recovery_with_valid_properties(self):
        """無効なエージェントプロパティを修正すると検証が通ること"""
        validator = AssignmentValidator()

        # Invalid state: empty name
        with pytest.raises(ValidationError):
            validator.validate_agent(
                name='',
                email='test@example.com',
                specialist_type='engineer',
            )

        # Recovery: provide valid properties
        validator.validate_agent(
            name='Valid Engineer',
            email='engineer@example.com',
            specialist_type='engineer',
        )


# ---------------------------------------------------------------------------
# テスト: Scenario 3 - Circular blockedBy
# ---------------------------------------------------------------------------

class TestCircularBlockedBy:
    """循環依存のリカバリーテスト"""

    def test_circular_dependency_2_way_raises_error(
        self, task_validator, mock_task_repo
    ):
        """2-wayの循環依存（A→B→A）はエラーになること"""
        task1 = MagicMock()
        task1.id = 1
        task2 = MagicMock()
        task2.id = 2

        mock_task_repo.get_instance_tasks.return_value = [task1, task2]

        dep1 = MagicMock()
        dep1.predecessor_id = 1
        dep1.successor_id = 2
        dep2 = MagicMock()
        dep2.predecessor_id = 2
        dep2.successor_id = 1

        mock_task_repo.get_task_dependencies.return_value = [dep1, dep2]

        with pytest.raises(CircularDependencyError) as exc_info:
            task_validator.validate_no_cycles(instance_id=1)

        assert 'Circular dependency' in str(exc_info.value)

    def test_circular_dependency_3_way_raises_error(
        self, task_validator, mock_task_repo
    ):
        """3-wayの循環依存（A→B→C→A）はエラーになること"""
        task1 = MagicMock()
        task1.id = 1
        task2 = MagicMock()
        task2.id = 2
        task3 = MagicMock()
        task3.id = 3

        mock_task_repo.get_instance_tasks.return_value = [task1, task2, task3]

        dep1 = MagicMock()
        dep1.predecessor_id = 1
        dep1.successor_id = 2
        dep2 = MagicMock()
        dep2.predecessor_id = 2
        dep2.successor_id = 3
        dep3 = MagicMock()
        dep3.predecessor_id = 3
        dep3.successor_id = 1

        mock_task_repo.get_task_dependencies.return_value = [dep1, dep2, dep3]

        with pytest.raises(CircularDependencyError) as exc_info:
            task_validator.validate_no_cycles(instance_id=1)

        assert 'Circular dependency' in str(exc_info.value)

    def test_circular_dependency_self_loop_raises_error(
        self, task_validator, mock_task_repo
    ):
        """自己参照（A→A）はエラーになること"""
        task1 = MagicMock()
        task1.id = 1

        mock_task_repo.get_instance_tasks.return_value = [task1]

        dep = MagicMock()
        dep.predecessor_id = 1
        dep.successor_id = 1

        mock_task_repo.get_task_dependencies.return_value = [dep]

        with pytest.raises(CircularDependencyError):
            task_validator.validate_no_cycles(instance_id=1)

    def test_valid_dag_no_cycles(self, task_validator, mock_task_repo):
        """有効なDAG（循環なし）はエラーにならないこと"""
        task1 = MagicMock()
        task1.id = 1
        task2 = MagicMock()
        task2.id = 2
        task3 = MagicMock()
        task3.id = 3

        mock_task_repo.get_instance_tasks.return_value = [task1, task2, task3]

        dep1 = MagicMock()
        dep1.predecessor_id = 1
        dep1.successor_id = 2
        dep2 = MagicMock()
        dep2.predecessor_id = 2
        dep2.successor_id = 3

        mock_task_repo.get_task_dependencies.return_value = [dep1, dep2]

        # Should not raise
        task_validator.validate_no_cycles(instance_id=1)

    def test_circular_dependency_recovery_remove_cycle(
        self, task_validator, mock_task_repo
    ):
        """循環参照を削除するとエラーが解消すること"""
        task1 = MagicMock()
        task1.id = 1
        task2 = MagicMock()
        task2.id = 2
        task3 = MagicMock()
        task3.id = 3

        mock_task_repo.get_instance_tasks.return_value = [task1, task2, task3]

        # Invalid state: circular dependency
        dep1 = MagicMock()
        dep1.predecessor_id = 1
        dep1.successor_id = 2
        dep2 = MagicMock()
        dep2.predecessor_id = 2
        dep2.successor_id = 3
        dep3 = MagicMock()
        dep3.predecessor_id = 3
        dep3.successor_id = 1

        mock_task_repo.get_task_dependencies.return_value = [dep1, dep2, dep3]

        with pytest.raises(CircularDependencyError):
            task_validator.validate_no_cycles(instance_id=1)

        # Recovery: remove circular dependency edge
        mock_task_repo.get_task_dependencies.return_value = [dep1, dep2]

        # Should not raise after removing the cycle
        task_validator.validate_no_cycles(instance_id=1)

    def test_circular_dependency_complex_graph(
        self, task_validator, mock_task_repo
    ):
        """複雑なグラフの中から循環を検出できること"""
        # Graph: 1→2→3, 4→5→3, 5→4 (cycle: 4→5→4)
        tasks = [MagicMock(id=i) for i in range(1, 6)]
        mock_task_repo.get_instance_tasks.return_value = tasks

        deps = [
            MagicMock(predecessor_id=1, successor_id=2),
            MagicMock(predecessor_id=2, successor_id=3),
            MagicMock(predecessor_id=4, successor_id=5),
            MagicMock(predecessor_id=5, successor_id=3),
            MagicMock(predecessor_id=5, successor_id=4),  # Cycle here
        ]
        mock_task_repo.get_task_dependencies.return_value = deps

        with pytest.raises(CircularDependencyError):
            task_validator.validate_no_cycles(instance_id=1)


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestErrorRecoveryIntegration:
    """複数のエラーシナリオのリカバリーテスト"""

    def test_recover_from_invalid_template_and_missing_specialist(
        self,
        template_validator,
        mock_template_repo,
    ):
        """テンプレート不正と割り当て不正の両方を修正できること"""
        # Step 1: Invalid template
        mock_template_repo.get_phases.return_value = []
        with pytest.raises(ValidationError):
            template_validator.validate_template_complete(template_id=1)

        # Step 2: Recovery - Fix template
        phase = Phase(
            id=1,
            template_id=1,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='engineer',
            phase_order=1,
        )
        task = TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key='task1',
            task_title='Task 1',
        )
        mock_template_repo.get_phases.return_value = [phase]
        mock_template_repo.get_tasks_for_phase.return_value = [task]

        # Template validation should pass now
        template_validator.validate_template_complete(template_id=1)

        # Step 3: Assignment validation
        validator = AssignmentValidator()
        phases = [phase]

        # Invalid: missing assignment
        with pytest.raises(ValidationError):
            validator.validate_all_phases_assigned(phases, {})

        # Recovery: add assignment
        assignments = {'phase1': 'engineer@example.com'}
        validator.validate_all_phases_assigned(phases, assignments)

    def test_all_three_errors_sequential_recovery(
        self,
        template_validator,
        task_validator,
        mock_template_repo,
        mock_task_repo,
    ):
        """3つのエラーをすべて検出・修正できること"""
        # Error 1: Invalid Template
        mock_template_repo.get_phases.return_value = []
        with pytest.raises(ValidationError):
            template_validator.validate_template_complete(template_id=1)

        # Error 2: Missing Specialist / Invalid Assignment
        validator = AssignmentValidator()
        phase = Phase(
            id=1,
            template_id=1,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='engineer',
            phase_order=1,
        )
        with pytest.raises(ValidationError):
            validator.validate_all_phases_assigned([phase], {})

        # Error 3: Circular Dependency
        task1 = MagicMock(id=1)
        task2 = MagicMock(id=2)
        mock_task_repo.get_instance_tasks.return_value = [task1, task2]
        dep1 = MagicMock(predecessor_id=1, successor_id=2)
        dep2 = MagicMock(predecessor_id=2, successor_id=1)
        mock_task_repo.get_task_dependencies.return_value = [dep1, dep2]
        with pytest.raises(CircularDependencyError):
            task_validator.validate_no_cycles(instance_id=1)

        # Recovery: Fix all three errors
        phase_fixed = Phase(
            id=1,
            template_id=1,
            phase_key='phase1',
            phase_label='Phase 1',
            specialist_type='engineer',
            phase_order=1,
        )
        task = TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key='task1',
            task_title='Task 1',
        )
        mock_template_repo.get_phases.return_value = [phase_fixed]
        mock_template_repo.get_tasks_for_phase.return_value = [task]
        mock_task_repo.get_task_dependencies.return_value = []

        # All validations should pass
        template_validator.validate_template_complete(template_id=1)
        validator.validate_all_phases_assigned([phase_fixed], {'phase1': 'engineer@example.com'})
        task_validator.validate_no_cycles(instance_id=1)
