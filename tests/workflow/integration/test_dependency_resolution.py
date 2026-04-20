"""Task dependency resolution integration tests"""

import pytest


class TestDependencyResolution:
    """タスク依存関係解決統合テスト"""

    def test_task_dependency_resolution(self, real_db):
        """Resolve task dependencies and verify blocking logic"""
        cursor = real_db.cursor()

        # Create agent
        cursor.execute("INSERT INTO agents (name, email, specialist_type) VALUES (?, ?, ?)",
                      ('Bob Smith', 'bob@example.com', 'engineer'))
        real_db.commit()
        agent_id = cursor.lastrowid

        # Create template
        cursor.execute("""
            INSERT INTO workflow_templates (name, description, status, created_by)
            VALUES (?, ?, ?, ?)
        """, ('Development Pipeline', 'Standard dev pipeline', 'draft', 'bob@example.com'))
        real_db.commit()
        template_id = cursor.lastrowid

        # Create phase
        cursor.execute("""
            INSERT INTO wf_template_phases
            (template_id, phase_key, phase_label, specialist_type, phase_order)
            VALUES (?, ?, ?, ?, ?)
        """, (template_id, 'development', 'Development', 'engineer', 1))
        real_db.commit()
        phase_id = cursor.lastrowid

        # Publish template
        cursor.execute('UPDATE workflow_templates SET status = ? WHERE id = ?', ('published', template_id))
        real_db.commit()

        # Create workflow instance
        cursor.execute("""
            INSERT INTO workflow_instances (template_id, name, status)
            VALUES (?, ?, ?)
        """, (template_id, 'Dev Pipeline #1', 'ready'))
        real_db.commit()
        instance_id = cursor.lastrowid

        # Assign specialist
        cursor.execute("""
            INSERT INTO workflow_instance_specialists
            (instance_id, phase_id, specialist_id, specialist_slug, specialist_name)
            VALUES (?, ?, ?, ?, ?)
        """, (instance_id, phase_id, agent_id, 'bob', 'Bob Smith'))
        real_db.commit()

        # Create dev_tasks with dependency chain
        cursor.execute("""
            INSERT INTO dev_tasks
            (title, description, assignee, phase, workflow_instance_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('Setup Environment', 'Setup dev environment', 'bob@example.com',
              'development', instance_id, 'pending'))
        real_db.commit()
        task1_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO dev_tasks
            (title, description, assignee, phase, workflow_instance_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('Write Code', 'Write application code', 'bob@example.com',
              'development', instance_id, 'blocked'))
        real_db.commit()
        task2_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO dev_tasks
            (title, description, assignee, phase, workflow_instance_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('Test Code', 'Test application code', 'bob@example.com',
              'development', instance_id, 'blocked'))
        real_db.commit()
        task3_id = cursor.lastrowid

        # Create dependency chain: task1 → task2 → task3
        cursor.execute("""
            INSERT INTO task_dependencies (predecessor_id, successor_id, dep_type)
            VALUES (?, ?, ?)
        """, (task1_id, task2_id, 'finish_to_start'))
        real_db.commit()

        cursor.execute("""
            INSERT INTO task_dependencies (predecessor_id, successor_id, dep_type)
            VALUES (?, ?, ?)
        """, (task2_id, task3_id, 'finish_to_start'))
        real_db.commit()

        # Verify dependency count
        cursor.execute('SELECT COUNT(*) FROM task_dependencies WHERE predecessor_id = ?', (task1_id,))
        assert cursor.fetchone()[0] == 1

        cursor.execute('SELECT COUNT(*) FROM task_dependencies WHERE predecessor_id = ?', (task2_id,))
        assert cursor.fetchone()[0] == 1

        # Verify task statuses (task1 pending, task2 and task3 blocked)
        cursor.execute('SELECT status FROM dev_tasks WHERE id = ?', (task1_id,))
        assert cursor.fetchone()[0] == 'pending'

        cursor.execute('SELECT status FROM dev_tasks WHERE id = ?', (task2_id,))
        assert cursor.fetchone()[0] == 'blocked'

        cursor.execute('SELECT status FROM dev_tasks WHERE id = ?', (task3_id,))
        assert cursor.fetchone()[0] == 'blocked'

        # Simulate task1 completion
        cursor.execute('UPDATE dev_tasks SET status = ? WHERE id = ?', ('completed', task1_id))
        real_db.commit()

        # Verify task1 is now complete
        cursor.execute('SELECT status FROM dev_tasks WHERE id = ?', (task1_id,))
        assert cursor.fetchone()[0] == 'completed'
