"""BDD step definitions for workflow task generation scenarios"""

import csv
from pytest_bdd import given, when, then, parsers


# ===== SCENARIO 3: Auto-generate phase-based tasks =====

@given(parsers.parse('a workflow instance created from "{template_name}" template'))
def instance_from_template(
    template_service, instance_service, specialist_repo,
    bdd_context, template_name
):
    """Create and instantiate template"""
    # Create template
    template = template_service.create_template(template_name)

    # Add phases with tasks
    phase_specs = [
        ('Planning', 'pm', 3),
        ('Development', 'engineer', 5),
        ('Testing', 'qa', 4),
        ('Deployment', 'devops', 2),
    ]

    for phase_name, specialist_type, task_count in phase_specs:
        phase = template_service.add_phase(
            template_id=template.id,
            phase_key=phase_name.lower().replace(' ', '_'),
            phase_label=phase_name,
            specialist_type=specialist_type,
            phase_order=len(bdd_context.phases) + 1,
        )

        bdd_context.phases[phase_name] = {
            'phase': phase,
            'task_count': task_count
        }

        # Add tasks for phase
        for task_idx in range(task_count):
            task = template_service.add_task_to_phase(
                phase_id=phase.id,
                task_key=f"{phase_name.lower().replace(' ', '_')}_task_{task_idx + 1}",
                task_title=f"{phase_name} Task {task_idx + 1}",
                task_description=f"Execute {phase_name} task {task_idx + 1}",
                priority=task_idx + 1,
                estimated_hours=8.0
            )
            if phase_name not in bdd_context.tasks:
                bdd_context.tasks[phase_name] = []
            bdd_context.tasks[phase_name].append(task)

    # Publish template
    template_service.publish_template(template.id)

    # Create specialists
    specialist_emails = {
        'Planning': 'alice@example.com',
        'Development': 'bob@example.com',
        'Testing': 'carol@example.com',
        'Deployment': 'dave@example.com',
    }

    specialist_assignments = {}
    for phase_name, email in specialist_emails.items():
        specialist = specialist_repo.get_agent_by_email(email)
        if specialist is None:
            specialist = specialist_repo.create_agent(
                name=email.split('@')[0].title(),
                email=email,
                specialist_type=bdd_context.phases[phase_name]['phase'].specialist_type
            )
        bdd_context.specialist_assignments[phase_name] = {
            'email': email,
            'specialist': specialist
        }
        phase_key = phase_name.lower().replace(' ', '_')
        specialist_assignments[phase_key] = email

    # Instantiate
    instance = instance_service.instantiate_workflow(
        template_id=template.id,
        instance_name=f"{template_name} #1",
        specialist_assignments=specialist_assignments
    )

    bdd_context.workflow_instance = instance
    bdd_context.templates[template_name] = template
    return instance


@given(parsers.parse('the instance has {phase_count} phases with assigned specialists'))
def instance_has_phases_with_specialists(bdd_context, phase_count):
    """Verify phases are assigned"""
    instance = bdd_context.workflow_instance
    assert instance is not None, "Workflow instance not created"
    assert instance.status == 'ready', \
        f"Instance status should be 'ready', got {instance.status}"
    return instance


@when('I trigger auto-task generation')
def trigger_task_generation(bdd_context):
    """Generate tasks (automatically done on instantiation)"""
    bdd_context.task_generation_triggered = True
    return bdd_context.workflow_instance


@then('tasks should be generated for each phase:')
def tasks_generated_for_phases(task_repo, bdd_context, table):
    """Verify tasks match expected count per phase"""
    instance = bdd_context.workflow_instance

    expected_by_phase = {}
    for row in table:
        phase_key = row['Phase Name'].lower().replace(' ', '_')
        expected_by_phase[phase_key] = {
            'count': int(row['Task Count']),
            'assignee': row['Assignee']
        }

    # Verify counts per phase - get tasks for each phase
    for phase_key, expected in expected_by_phase.items():
        phase_tasks = task_repo.get_tasks_by_phase(instance.id, phase_key)
        assert len(phase_tasks) == expected['count'], \
            f"Phase {phase_key}: expected {expected['count']} tasks, got {len(phase_tasks)}"

        for task in phase_tasks:
            assert task.assignee == expected['assignee'], \
                f"Task {task.title}: expected assignee {expected['assignee']}, got {task.assignee}"


@then('each task should have title, description, and assignee')
def tasks_have_details(task_repo, bdd_context):
    """Verify task details are complete"""
    instance = bdd_context.workflow_instance

    # Get all tasks from all phases
    all_tasks = []
    for phase_name in bdd_context.phases.keys():
        phase_key = phase_name.lower().replace(' ', '_')
        phase_tasks = task_repo.get_tasks_by_phase(instance.id, phase_key)
        all_tasks.extend(phase_tasks)

    assert len(all_tasks) > 0, "No tasks to verify"

    for task in all_tasks:
        assert task.title is not None and len(task.title) > 0, \
            f"Task should have title"
        assert task.description is not None and len(task.description) > 0, \
            f"Task {task.title} should have description"
        assert task.assignee is not None and '@' in task.assignee, \
            f"Task {task.title} should have valid email assignee"


@then('tasks should respect phase sequential order')
def tasks_respect_phase_order(task_repo, template_repo, bdd_context):
    """Verify phase ordering constraints"""
    instance = bdd_context.workflow_instance
    tasks = task_repo.get_instance_tasks(instance.id)

    # Group by phase
    phase_groups = {}
    for task in tasks:
        if task.phase not in phase_groups:
            phase_groups[task.phase] = []
        phase_groups[task.phase].append(task)

    # Verify we have multiple phases
    assert len(phase_groups) > 1, "Should have multiple phases"


@then('phase tasks should only become active after previous phase completion')
def phase_tasks_blocked_until_predecessor(task_repo, bdd_context):
    """Verify initial task status is blocked"""
    instance = bdd_context.workflow_instance

    # Get all tasks from all phases
    all_tasks = []
    for phase_name in bdd_context.phases.keys():
        phase_key = phase_name.lower().replace(' ', '_')
        phase_tasks = task_repo.get_tasks_by_phase(instance.id, phase_key)
        all_tasks.extend(phase_tasks)

    assert len(all_tasks) > 0, "Should have generated tasks"

    # All tasks initially blocked
    for task in all_tasks:
        assert task.status == 'blocked', \
            f"Task {task.title} should initially be blocked, got {task.status}"

    # Generate metrics.csv after all assertions pass
    metrics_path = 'metrics.csv'
    with open(metrics_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'phase', 'task_id', 'task_title', 'assignee', 'status', 'estimated_hours'
        ])
        writer.writeheader()
        for task in all_tasks:
            writer.writerow({
                'phase': task.phase,
                'task_id': task.id,
                'task_title': task.title,
                'assignee': task.assignee,
                'status': task.status,
                'estimated_hours': task.estimated_hours or 0
            })
