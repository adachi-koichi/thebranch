"""Instantiation workflow integration tests"""

import pytest
from datetime import datetime


class TestInstantiationWorkflow:
    """インスタンス化ワークフロー統合テスト"""

    def test_create_instance_from_template(self, services, created_agents):
        """テンプレートからインスタンスを作成"""
        template_svc = services['template']
        instance_svc = services['instance']

        # Create and publish template
        template = template_svc.create_template(
            name='Product Launch',
            description='Standard product launch process',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='plan',
            task_title='Planning',
            task_description='Plan the product launch'
        )

        template_svc.publish_template(template.id)

        # Create instance via instantiate_workflow
        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Product Launch #1',
            specialist_assignments={'planning': created_agents['alice'].id},
            context={'product': 'New App', 'target': 'Q2 2026'}
        )

        assert instance is not None
        assert instance.template_id == template.id
        assert instance.name == 'Product Launch #1'
        assert instance.status == 'ready'

    def test_full_instantiation_workflow(self, services, created_agents):
        """
        Full workflow: Create template → Publish → Instantiate → Assign specialists → Generate tasks
        """
        template_svc = services['template']
        instance_svc = services['instance']

        # Step 1: Create template with phases
        template = template_svc.create_template(
            name='Full Pipeline',
            description='Complete workflow pipeline',
            created_by='alice@example.com'
        )

        planning_phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1
        )

        dev_phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='development',
            phase_label='Development',
            specialist_type='engineer',
            phase_order=2
        )

        # Step 2: Add tasks to phases
        task1 = template_svc.add_task_to_phase(
            phase_id=planning_phase.id,
            task_key='requirements',
            task_title='Gather Requirements',
            task_description='Collect project requirements'
        )

        task2 = template_svc.add_task_to_phase(
            phase_id=dev_phase.id,
            task_key='implement',
            task_title='Implement Feature',
            task_description='Build core feature',
            depends_on_key=None
        )

        # Step 3: Publish template
        template_svc.publish_template(template.id)

        # Step 4 & 5 & 6: Instantiate workflow (combines create instance, assign specialists, generate tasks)
        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Project Phase 1',
            specialist_assignments={
                'planning': created_agents['alice'].id,
                'development': created_agents['bob'].id
            },
            context={'sprint': '1', 'team_size': '5'}
        )

        assert instance is not None
        assert instance.template_id == template.id
        assert instance.status == 'ready'

    def test_instance_with_context_variables(self, services, created_agents):
        """コンテキスト変数を持つインスタンス化"""
        template_svc = services['template']
        instance_svc = services['instance']

        template = template_svc.create_template(
            name='Context Template',
            description='Template with context',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='plan',
            task_title='Planning',
            task_description='Plan the project'
        )

        template_svc.publish_template(template.id)

        context = {
            'project_name': 'AI Orchestrator',
            'target_date': '2026-06-30',
            'budget': '100k',
            'team_members': 3
        }

        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='AI Orch Phase 1',
            specialist_assignments={'planning': created_agents['alice'].id},
            context=context
        )

        assert instance.context is not None
        # Context should be preserved
        retrieved = instance_svc.get_instance(instance.id)
        assert retrieved.context is not None

    def test_instance_state_transitions(self, services, created_agents):
        """インスタンスの状態遷移テスト"""
        template_svc = services['template']
        instance_svc = services['instance']

        template = template_svc.create_template(
            name='Transition Template',
            description='Test state transitions',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='plan',
            task_title='Planning',
            task_description='Plan the project'
        )

        template_svc.publish_template(template.id)

        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Transition Test',
            specialist_assignments={'planning': created_agents['alice'].id},
            context={}
        )

        # After instantiate_workflow, status should be 'ready'
        assert instance.status == 'ready'

        # Can retrieve instance and check status
        retrieved = instance_svc.get_instance(instance.id)
        assert retrieved.status == 'ready'

    def test_multiple_instances_same_template(self, services, created_agents):
        """同一テンプレートから複数のインスタンスを作成"""
        template_svc = services['template']
        instance_svc = services['instance']

        template = template_svc.create_template(
            name='Reusable Template',
            description='Can be instantiated multiple times',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='plan',
            task_title='Planning',
            task_description='Plan the project'
        )

        template_svc.publish_template(template.id)

        # Create 3 instances
        instances = []
        for i in range(3):
            instance = instance_svc.instantiate_workflow(
                template_id=template.id,
                instance_name=f'Instance {i+1}',
                specialist_assignments={'planning': created_agents['alice'].id},
                context={'iteration': i+1}
            )
            instances.append(instance)

        assert len(instances) == 3
        assert all(inst.template_id == template.id for inst in instances)
        assert all(inst.status == 'ready' for inst in instances)

    def test_instance_retrieval_by_template(self, services, created_agents):
        """テンプレートからインスタンス一覧を取得"""
        template_svc = services['template']
        instance_svc = services['instance']

        template = template_svc.create_template(
            name='Template for List',
            description='To be instantiated multiple times',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='planning',
            phase_label='Planning',
            specialist_type='pm',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='plan',
            task_title='Planning',
            task_description='Plan the project'
        )

        template_svc.publish_template(template.id)

        # Create instances
        instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Instance A',
            specialist_assignments={'planning': created_agents['alice'].id},
            context={}
        )
        instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Instance B',
            specialist_assignments={'planning': created_agents['alice'].id},
            context={}
        )

        # List instances for template
        instances = instance_svc.list_instances(template_id=template.id)
        assert len(instances) >= 2
        assert all(inst.template_id == template.id for inst in instances)
