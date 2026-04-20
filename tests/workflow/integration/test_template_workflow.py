"""Template lifecycle integration tests"""

import pytest
from datetime import datetime


class TestTemplateWorkflow:
    """テンプレートライフサイクル統合テスト"""

    def test_template_create_via_service(self, services):
        """Service層を使ったテンプレート作成"""
        template_svc = services['template']

        template = template_svc.create_template(
            name='Product Launch',
            description='Standard product launch process',
            created_by='alice@example.com'
        )

        assert template is not None
        assert template.name == 'Product Launch'
        assert template.status == 'draft'
        assert template.created_by == 'alice@example.com'

    def test_template_complete_lifecycle(self, services):
        """
        Create → Add phases → Add tasks → Publish（Service層統合）
        """
        template_svc = services['template']

        # Step 1: Create template
        template = template_svc.create_template(
            name='Product Launch',
            description='Standard product launch process',
            created_by='alice@example.com'
        )
        template_id = template.id

        # Step 2: Add phases
        planning_phase = template_svc.add_phase(
            template_id=template_id,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1
        )
        dev_phase = template_svc.add_phase(
            template_id=template_id,
            phase_key='development',
            phase_label='Development',
            specialist_type='engineer',
            phase_order=2
        )
        template = template_svc.get_template(template_id)

        assert planning_phase.phase_key == 'planning'
        assert dev_phase.phase_key == 'development'

        # Step 3: Add tasks to each phase
        task1 = template_svc.add_task_to_phase(
            phase_id=planning_phase.id,
            task_key='plan_requirements',
            task_title='Plan Requirements',
            task_description='Define project requirements'
        )
        task2 = template_svc.add_task_to_phase(
            phase_id=dev_phase.id,
            task_key='dev_feature',
            task_title='Develop Feature',
            task_description='Implement core feature'
        )

        assert task1.task_key == 'plan_requirements'
        assert task2.task_key == 'dev_feature'

        # Step 4: Publish template
        updated_template = template_svc.publish_template(template_id)
        assert updated_template.status == 'published'

        # Verify full lifecycle
        final_template = template_svc.get_template(template_id)
        assert final_template.status == 'published'

        assert len(final_template.phases) == 2

        task_count = sum(len(phase.tasks) for phase in final_template.phases)
        assert task_count == 2

    def test_template_with_task_dependencies(self, services):
        """依存関係を持つタスク定義のテスト"""
        template_svc = services['template']

        # Create template with dependencies
        template = template_svc.create_template(
            name='Pipeline with Dependencies',
            description='Sequential pipeline',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='main',
            phase_label='Main',
            specialist_type='engineer',
            phase_order=1
        )

        # Task 1: no dependencies
        task1 = template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='setup',
            task_title='Setup',
            task_description='Setup project'
        )

        # Task 2: depends on task1
        task2 = template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='implementation',
            task_title='Implementation',
            task_description='Implement features',
            depends_on_key='setup'
        )

        # Task 3: depends on task2
        task3 = template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='testing',
            task_title='Testing',
            task_description='Test implementation',
            depends_on_key='implementation'
        )

        assert task1.depends_on_key is None
        assert task2.depends_on_key == 'setup'
        assert task3.depends_on_key == 'implementation'

    def test_template_retrieve_and_list(self, services):
        """テンプレートの取得・一覧表示"""
        template_svc = services['template']

        # Create multiple templates
        t1 = template_svc.create_template('Template 1', 'Desc 1', 'alice@example.com')
        t2 = template_svc.create_template('Template 2', 'Desc 2', 'bob@example.com')

        # List all templates
        all_templates = template_svc.list_templates()
        assert len(all_templates) >= 2

        # Retrieve specific template
        retrieved = template_svc.get_template(t1.id)
        assert retrieved.name == 'Template 1'
        assert retrieved.created_by == 'alice@example.com'
