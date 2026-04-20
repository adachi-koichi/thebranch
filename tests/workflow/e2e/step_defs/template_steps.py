"""BDD step definitions for workflow template scenarios"""

import pytest
from pytest_bdd import given, when, then, parsers
from tests.workflow.e2e.conftest import normalize_specialist_type


# ===== SCENARIO 1: Create workflow template =====

@given(parsers.parse('a workflow template named "{template_name}"'))
def workflow_template_named(template_service, bdd_context, template_name):
    """Create template with given name"""
    template = template_service.create_template(
        name=template_name,
        created_by="test@example.com"
    )
    bdd_context.templates[template_name] = template
    bdd_context.current_template_name = template_name
    return template


@given(parsers.parse('the template has description "{description}"'))
def template_has_description(template_service, bdd_context, description):
    """Update template description"""
    template_name = bdd_context.current_template_name
    template = bdd_context.templates[template_name]
    template.description = description
    template_service.template_repo.update_template(template)


@given('the template defines the following phases:')
def template_defines_phases(workflow_template_named, template_service, bdd_context, table):
    """Create phases from Gherkin table"""
    template = workflow_template_named

    for row in table:
        phase = template_service.add_phase(
            template_id=template.id,
            phase_key=row['Phase Name'].lower().replace(' ', '_'),
            phase_label=row['Phase Name'],
            specialist_type=normalize_specialist_type(row['Specialist Type']),
            phase_order=len(bdd_context.phases) + 1,
            is_parallel=row['Sequential'].lower() == 'false'
        )
        phase_name = row['Phase Name']
        bdd_context.phases[phase_name] = {
            'phase': phase,
            'task_count': int(row['Task Count'])
        }

        # Add sample tasks for each phase
        for task_idx in range(int(row['Task Count'])):
            task = template_service.add_task_to_phase(
                phase_id=phase.id,
                task_key=f"{row['Phase Name'].lower().replace(' ', '_')}_task_{task_idx + 1}",
                task_title=f"{row['Phase Name']} Task {task_idx + 1}",
                task_description=f"Execute {row['Phase Name']} task {task_idx + 1}",
                priority=task_idx + 1,
                estimated_hours=8.0
            )
            if phase_name not in bdd_context.tasks:
                bdd_context.tasks[phase_name] = []
            bdd_context.tasks[phase_name].append(task)

    return template


@when('I create the workflow template')
def create_workflow_template(bdd_context):
    """Trigger template creation (already done in Given)"""
    pass


@then('the template should be stored with ID')
def template_stored_with_id(workflow_template_named):
    """Verify template has ID"""
    assert workflow_template_named.id is not None, "Template ID should not be None"


@then(parsers.parse('the template should contain {phase_count} phases in order'))
def template_contains_phases(workflow_template_named, template_repo, phase_count):
    """Verify phase count and order"""
    phases = template_repo.get_phases(workflow_template_named.id)

    assert len(phases) == int(phase_count), \
        f"Expected {phase_count} phases, got {len(phases)}"

    # Verify order
    for i, phase in enumerate(phases):
        assert phase.phase_order == i + 1, \
            f"Phase {i} order should be {i+1}, got {phase.phase_order}"


@then('each phase should have defined task templates')
def each_phase_has_tasks(workflow_template_named, template_repo):
    """Verify each phase has at least one task"""
    phases = template_repo.get_phases(workflow_template_named.id)

    for phase in phases:
        tasks = template_repo.get_tasks_for_phase(phase.id)
        assert len(tasks) > 0, \
            f"Phase {phase.phase_label} ({phase.id}) should have tasks"


@when('I publish the template')
def publish_template(template_service, bdd_context):
    """Publish template"""
    template_name = bdd_context.current_template_name
    template = bdd_context.templates[template_name]
    template_service.publish_template(template.id)


@then(parsers.parse('the template status should be "{status}"'))
def template_has_status(workflow_template_named, template_repo, status):
    """Verify template status"""
    template = template_repo.get_template(workflow_template_named.id)
    assert template.status == status, \
        f"Template status should be {status}, got {template.status}"
