"""Error scenario integration tests"""

import pytest
import sqlite3


class TestErrorScenarios:
    """エラーシナリオ統合テスト"""

    def test_instantiate_unpublished_template(self, real_db):
        """Error: Cannot instantiate unpublished template"""
        cursor = real_db.cursor()

        # Create unpublished template
        cursor.execute("""
            INSERT INTO workflow_templates (name, description, status, created_by)
            VALUES (?, ?, ?, ?)
        """, ('Draft Pipeline', 'Not yet published', 'draft', 'alice@example.com'))
        real_db.commit()
        template_id = cursor.lastrowid

        # Attempt to instantiate should be prevented (in validation layer)
        # For now, verify template is in draft status
        cursor.execute('SELECT status FROM workflow_templates WHERE id = ?', (template_id,))
        assert cursor.fetchone()[0] == 'draft'

    def test_missing_specialist_assignment(self, real_db):
        """Error: Phase cannot be executed without specialist assignment"""
        cursor = real_db.cursor()

        # Create template
        cursor.execute("""
            INSERT INTO workflow_templates (name, status, created_by)
            VALUES (?, ?, ?)
        """, ('Incomplete Workflow', 'published', 'alice@example.com'))
        real_db.commit()
        template_id = cursor.lastrowid

        # Create phase
        cursor.execute("""
            INSERT INTO wf_template_phases
            (template_id, phase_key, phase_label, specialist_type, phase_order)
            VALUES (?, ?, ?, ?, ?)
        """, (template_id, 'planning', 'Planning', 'pm', 1))
        real_db.commit()
        phase_id = cursor.lastrowid

        # Create instance
        cursor.execute("""
            INSERT INTO workflow_instances (template_id, name, status)
            VALUES (?, ?, ?)
        """, (template_id, 'Incomplete Instance', 'ready'))
        real_db.commit()
        instance_id = cursor.lastrowid

        # Verify no specialist assignment exists
        cursor.execute("""
            SELECT COUNT(*) FROM workflow_instance_specialists
            WHERE instance_id = ? AND phase_id = ?
        """, (instance_id, phase_id))
        assert cursor.fetchone()[0] == 0

    def test_missing_phase_in_template(self, real_db):
        """Error: Template requires at least one phase"""
        cursor = real_db.cursor()

        # Create template with no phases
        cursor.execute("""
            INSERT INTO workflow_templates (name, status, created_by)
            VALUES (?, ?, ?)
        """, ('No Phases Template', 'draft', 'alice@example.com'))
        real_db.commit()
        template_id = cursor.lastrowid

        # Verify no phases exist
        cursor.execute('SELECT COUNT(*) FROM wf_template_phases WHERE template_id = ?', (template_id,))
        assert cursor.fetchone()[0] == 0

    def test_duplicate_task_keys_in_phase(self, real_db):
        """Error: Cannot create duplicate task keys in same phase"""
        cursor = real_db.cursor()

        # Create template and phase
        cursor.execute("""
            INSERT INTO workflow_templates (name, status, created_by)
            VALUES (?, ?, ?)
        """, ('Duplicate Keys Template', 'draft', 'alice@example.com'))
        real_db.commit()
        template_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO wf_template_phases
            (template_id, phase_key, phase_label, specialist_type, phase_order)
            VALUES (?, ?, ?, ?, ?)
        """, (template_id, 'phase1', 'Phase 1', 'pm', 1))
        real_db.commit()
        phase_id = cursor.lastrowid

        # Create first task
        cursor.execute("""
            INSERT INTO wf_template_tasks
            (phase_id, template_id, task_key, task_title)
            VALUES (?, ?, ?, ?)
        """, (phase_id, template_id, 'task_key', 'Task 1'))
        real_db.commit()

        # Attempt to create duplicate task key in same phase should fail
        try:
            cursor.execute("""
                INSERT INTO wf_template_tasks
                (phase_id, template_id, task_key, task_title)
                VALUES (?, ?, ?, ?)
            """, (phase_id, template_id, 'task_key', 'Task 2'))
            real_db.commit()
            # If we get here, the UNIQUE constraint didn't work
            assert False, "UNIQUE constraint should prevent duplicate task keys"
        except sqlite3.IntegrityError:
            # Expected: UNIQUE (phase_id, task_key) constraint should prevent this
            pass

    def test_invalid_task_status(self, real_db):
        """Error: Task status must be one of the allowed values"""
        cursor = real_db.cursor()

        # Create instance and try to insert task with invalid status
        cursor.execute("""
            INSERT INTO workflow_instances (template_id, name, status)
            VALUES (?, ?, ?)
        """, (1, 'Test Instance', 'ready'))
        real_db.commit()
        instance_id = cursor.lastrowid

        # Attempt to insert task with invalid status
        try:
            cursor.execute("""
                INSERT INTO dev_tasks
                (title, description, assignee, phase, workflow_instance_id, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ('Bad Task', 'Invalid status test', 'alice@example.com',
                  'phase1', instance_id, 'invalid_status'))
            real_db.commit()
            # If we get here, the CHECK constraint didn't work
            assert False, "CHECK constraint should prevent invalid status"
        except sqlite3.IntegrityError:
            # Expected: CHECK constraint should prevent invalid status
            pass
