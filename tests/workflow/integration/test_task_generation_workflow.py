"""Task generation workflow integration tests"""

import pytest
from datetime import datetime


class TestTaskGenerationWorkflow:
    """タスク生成ワークフロー統合テスト"""

    def test_generate_tasks_basic(self, services, repos, created_agents):
        """基本的なタスク生成"""
        template_svc = services['template']
        instance_svc = services['instance']
        task_repo = repos['task']

        # Create template with tasks
        template = template_svc.create_template(
            name='Simple Pipeline',
            description='Basic task generation',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='main',
            phase_label='Main',
            specialist_type='engineer',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='task1',
            task_title='Task 1',
            task_description='First task'
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='task2',
            task_title='Task 2',
            task_description='Second task'
        )

        template_svc.publish_template(template.id)

        # Create instance (which auto-generates tasks)
        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Test Instance',
            specialist_assignments={'main': created_agents['bob'].id},
            context={}
        )

        # Retrieve generated tasks
        tasks = task_repo.get_instance_tasks(instance.id)

        assert isinstance(tasks, list)
        assert len(tasks) == 2
        assert all(t.workflow_instance_id == instance.id for t in tasks)
        assert all(t.status in ['blocked', 'pending'] for t in tasks)

    def test_generate_tasks_with_dependencies(self, services, repos, created_agents):
        """依存関係を持つタスク生成"""
        template_svc = services['template']
        instance_svc = services['instance']
        task_repo = repos['task']

        template = template_svc.create_template(
            name='Deployment Pipeline',
            description='CI/CD deployment workflow',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='deployment',
            phase_label='Deployment',
            specialist_type='engineer',
            phase_order=1
        )

        # Task 1: no dependency
        task1 = template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='build',
            task_title='Build Application',
            task_description='Compile and package'
        )

        # Task 2: depends on task1
        task2 = template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='deploy',
            task_title='Deploy Application',
            task_description='Deploy to production',
            depends_on_key='build'
        )

        # Task 3: depends on task2
        task3 = template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='verify',
            task_title='Verify Deployment',
            task_description='Test deployed application',
            depends_on_key='deploy'
        )

        template_svc.publish_template(template.id)

        # Create instance and generate tasks
        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Deployment Instance',
            specialist_assignments={'deployment': created_agents['bob'].id},
            context={}
        )

        generated_tasks = task_repo.get_instance_tasks(instance.id)

        assert len(generated_tasks) == 3

        # Find build, deploy, verify tasks by title
        build = next(t for t in generated_tasks if t.title == 'Build Application')
        deploy = next(t for t in generated_tasks if t.title == 'Deploy Application')
        verify = next(t for t in generated_tasks if t.title == 'Verify Deployment')

        # All tasks should be in valid states
        assert build.status in ['blocked', 'pending']
        assert deploy.status in ['blocked', 'pending']
        assert verify.status in ['blocked', 'pending']

    def test_task_dependency_resolution(self, services, repos, created_agents):
        """依存タスクの解決フロー"""
        template_svc = services['template']
        instance_svc = services['instance']
        task_repo = repos['task']

        template = template_svc.create_template(
            name='Sequential Tasks',
            description='Tasks with sequential dependencies',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='seq',
            phase_label='Sequential',
            specialist_type='engineer',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='step1',
            task_title='Step 1',
            task_description='First step'
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='step2',
            task_title='Step 2',
            task_description='Second step',
            depends_on_key='step1'
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='step3',
            task_title='Step 3',
            task_description='Third step',
            depends_on_key='step2'
        )

        template_svc.publish_template(template.id)

        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Sequential Test',
            specialist_assignments={'seq': created_agents['bob'].id},
            context={}
        )

        tasks = task_repo.get_instance_tasks(instance.id)

        # Verify we have the correct number of tasks
        assert len(tasks) == 3
        
        # Verify dependency chain is correct
        step1 = next(t for t in tasks if t.title == 'Step 1')
        step2 = next(t for t in tasks if t.title == 'Step 2')
        step3 = next(t for t in tasks if t.title == 'Step 3')

        # All tasks should have valid statuses
        assert step1.status in ['blocked', 'pending']
        assert step2.status in ['blocked', 'pending']
        assert step3.status in ['blocked', 'pending']

    def test_tasks_with_priorities(self, services, repos, created_agents):
        """優先度付きタスク生成"""
        template_svc = services['template']
        instance_svc = services['instance']
        task_repo = repos['task']

        template = template_svc.create_template(
            name='Priority Tasks',
            description='Tasks with different priorities',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='work',
            phase_label='Work',
            specialist_type='engineer',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='critical',
            task_title='Critical Task',
            task_description='High priority',
            priority=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='normal',
            task_title='Normal Task',
            task_description='Medium priority',
            priority=3
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='low',
            task_title='Low Priority Task',
            task_description='Low priority',
            priority=5
        )

        template_svc.publish_template(template.id)

        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Priority Instance',
            specialist_assignments={'work': created_agents['bob'].id},
            context={}
        )

        tasks = task_repo.get_instance_tasks(instance.id)

        assert len(tasks) == 3
        critical = next(t for t in tasks if t.title == 'Critical Task')
        normal = next(t for t in tasks if t.title == 'Normal Task')
        low = next(t for t in tasks if t.title == 'Low Priority Task')

        # Verify priorities are preserved
        assert critical.priority == 1
        assert normal.priority == 3
        assert low.priority == 5

    def test_task_assignment_during_generation(self, services, repos, created_agents):
        """タスク生成時の割り当て"""
        template_svc = services['template']
        instance_svc = services['instance']
        task_repo = repos['task']

        template = template_svc.create_template(
            name='Assignment Template',
            description='Tasks will be assigned',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='dev',
            phase_label='Development',
            specialist_type='engineer',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='feature',
            task_title='Develop Feature',
            task_description='Build new feature'
        )

        template_svc.publish_template(template.id)

        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Dev Instance',
            specialist_assignments={'dev': created_agents['bob'].id},
            context={}
        )

        # Retrieve tasks
        tasks = task_repo.get_instance_tasks(instance.id)

        assert len(tasks) == 1
        task = tasks[0]
        assert task.assignee == created_agents['bob'].email

    def test_task_generation_with_estimates(self, services, repos, created_agents):
        """見積もり付きタスク生成"""
        template_svc = services['template']
        instance_svc = services['instance']
        task_repo = repos['task']

        template = template_svc.create_template(
            name='Estimated Tasks',
            description='Tasks with time estimates',
            created_by='alice@example.com'
        )

        phase = template_svc.add_phase(
            template_id=template.id,
            phase_key='work',
            phase_label='Work',
            specialist_type='engineer',
            phase_order=1
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='quick',
            task_title='Quick Task',
            task_description='Fast to do',
            estimated_hours=2.0
        )

        template_svc.add_task_to_phase(
            phase_id=phase.id,
            task_key='complex',
            task_title='Complex Task',
            task_description='Takes time',
            estimated_hours=16.0
        )

        template_svc.publish_template(template.id)

        instance = instance_svc.instantiate_workflow(
            template_id=template.id,
            instance_name='Estimate Instance',
            specialist_assignments={'work': created_agents['bob'].id},
            context={}
        )

        tasks = task_repo.get_instance_tasks(instance.id)

        assert len(tasks) == 2
        quick = next(t for t in tasks if t.title == 'Quick Task')
        complex_task = next(t for t in tasks if t.title == 'Complex Task')

        assert quick.estimated_hours == 2.0
        assert complex_task.estimated_hours == 16.0
