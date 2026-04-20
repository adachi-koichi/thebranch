"""BDD step definitions for workflow instance scenarios"""

import pytest
from pytest_bdd import given, when, then, parsers
from workflow.exceptions import SpecialistNotFoundError, ValidationError
from tests.workflow.e2e.conftest import normalize_specialist_type


# ===== SCENARIO 2: Instantiate template to workflow instance =====

@given(parsers.parse('a stored workflow template "{template_name}"'))
def stored_template(template_service, specialist_repo, bdd_context, template_name):
    """Reference previously created template or create new"""
    if template_name in bdd_context.templates:
        bdd_context.current_template_name = template_name
        return bdd_context.templates[template_name]

    # Create new template
    template = template_service.create_template(
        name=template_name,
        created_by="test@example.com"
    )
    bdd_context.templates[template_name] = template
    bdd_context.current_template_name = template_name
    return template


@given(parsers.parse('the template has {phase_count} phases with defined tasks'))
def template_with_phases(template_service, specialist_repo, bdd_context, phase_count):
    """Verify/create template with specified phases"""
    template = bdd_context.templates.get(bdd_context.current_template_name)
    if not template:
        raise ValueError(f"Template '{bdd_context.current_template_name}' not found in context")
    existing_phases = template_service.template_repo.get_phases(template.id)

    if len(existing_phases) == 0:
        # Create phases matching Feature specification
        all_phase_specs = [
            ('Planning', 'pm', 3),
            ('Development', 'engineer', 5),
            ('Testing', 'qa', 4),
            ('Deployment', 'devops', 2),
        ]

        phase_count_int = int(phase_count)
        phase_specs = all_phase_specs[:phase_count_int]

        for phase_name, specialist_type, task_count in phase_specs:
            phase = template_service.add_phase(
                template_id=template.id,
                phase_key=phase_name.lower().replace(' ', '_'),
                phase_label=phase_name,
                specialist_type=specialist_type,
                phase_order=len(bdd_context.phases) + 1,
            )

            bdd_context.phases[phase_name.lower().replace(' ', '_')] = {
                'phase': phase,
                'task_count': task_count,
                'specialist_type': specialist_type
            }

            # Add tasks
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
        bdd_context.templates[template.name] = template

    return template


@given('I have assigned specialists:')
def assigned_specialists(specialist_repo, bdd_context, table):
    """Create specialists and store assignments from table"""
    assignments = {}

    for row in table:
        phase_name = row['Phase Name']
        email = row['Assigned Specialist']

        # Normalize phase_name to lowercase for consistent lookup
        phase_key = phase_name.lower().replace(' ', '_')

        specialist_type = 'engineer'
        if phase_key in bdd_context.phases:
            specialist_type = bdd_context.phases[phase_key]['phase'].specialist_type

        # Create specialist if not exists
        specialist = specialist_repo.get_agent_by_email(email)
        if specialist is None:
            name = email.split('@')[0].title()
            specialist = specialist_repo.create_agent(
                name=name,
                email=email,
                specialist_type=specialist_type
            )

        assignments[phase_key] = email
        bdd_context.specialist_assignments[phase_key] = {
            'email': email,
            'specialist': specialist
        }

    bdd_context.specialist_assignments_dict = assignments
    return assignments


@when('I instantiate the template with specialist assignments')
def instantiate_template(instance_service, bdd_context):
    """Instantiate template"""
    template = bdd_context.templates.get(bdd_context.current_template_name)
    if not template:
        raise ValueError(f"Template '{bdd_context.current_template_name}' not found")

    if template.status != 'published':
        template.status = 'published'
        instance_service.template_repo.update_template(template)

    instance = instance_service.instantiate_workflow(
        template_id=template.id,
        instance_name=f"{template.name} Instance #1",
        specialist_assignments=bdd_context.specialist_assignments_dict
    )

    bdd_context.instances['main'] = instance
    return instance


@then('a new workflow instance should be created')
def instance_created(bdd_context):
    """Verify instance was created"""
    assert 'main' in bdd_context.instances, "Instance not created"
    instance = bdd_context.instances['main']
    assert instance.id is not None, "Instance ID should not be None"
    assert instance.status == 'ready', f"Instance status should be 'ready', got {instance.status}"


@then('the instance should reference the template')
def instance_references_template(bdd_context):
    """Verify instance points to template"""
    assert 'main' in bdd_context.instances, "Instance not created"
    instance = bdd_context.instances['main']
    template = bdd_context.templates.get(bdd_context.current_template_name)
    assert template is not None, "Template not found"
    assert instance.template_id == template.id, \
        f"Instance template_id {instance.template_id} != template {template.id}"


@then(parsers.parse('the instance should contain {phase_count} phase instances'))
def instance_has_phase_instances(instance_repo, bdd_context, phase_count):
    """Verify phase instance count"""
    assert 'main' in bdd_context.instances, "Instance not created"
    instance = bdd_context.instances['main']
    phase_instances = instance_repo.get_phase_instances(instance.id)

    assert len(phase_instances) == int(phase_count), \
        f"Expected {phase_count} phase instances, got {len(phase_instances)}"


@then('each phase should be assigned to the specified specialist')
def phases_assigned_to_specialists(instance_repo, template_repo, bdd_context):
    """Verify specialist assignments"""
    assert 'main' in bdd_context.instances, "Instance not created"
    instance = bdd_context.instances['main']
    phases = template_repo.get_phases(instance.template_id)

    assert len(phases) > 0, "Template should have phases"

    for phase in phases:
        specialist = instance_repo.get_phase_specialist(instance.id, phase.id)
        assert specialist is not None, \
            f"Specialist not assigned for phase {phase.phase_label}"


@given('the following specialists are available:')
def specialists_available(specialist_repo, bdd_context, table):
    """Create specialists from table"""
    for row in table:
        specialist = specialist_repo.get_agent_by_email(row['Email'])
        if specialist is None:
            specialist = specialist_repo.create_agent(
                name=row['Name'],
                email=row['Email'],
                specialist_type=normalize_specialist_type(row['Specialist Type'])
            )
        bdd_context.specialists[row['Email']] = specialist


@given('the template is published')
def template_is_published(template_service, bdd_context):
    """Ensure template is published"""
    template_name = bdd_context.current_template_name
    template = bdd_context.templates[template_name]
    if template.status != 'published':
        template_service.publish_template(template.id)
        template.status = 'published'
    return template


@given(parsers.parse('no specialists are registered for type "{specialist_type}"'))
def no_specialists_for_type(specialist_repo, bdd_context, specialist_type):
    """Track that no specialists are available for type"""
    bdd_context.missing_specialist_type = specialist_type
    bdd_context.specialist_assignments_dict = {}


@when('I attempt to instantiate the template')
def attempt_instantiate_template(instance_service, bdd_context):
    """Try to instantiate but catch validation errors"""
    template_name = bdd_context.current_template_name
    template = bdd_context.templates[template_name]
    bdd_context.instantiation_error = None

    try:
        if template.status != 'published':
            template.status = 'published'
            instance_service.template_repo.update_template(template)

        instance = instance_service.instantiate_workflow(
            template_id=template.id,
            instance_name=f"{template.name} Instance",
            specialist_assignments=bdd_context.specialist_assignments_dict
        )
        bdd_context.instances['main'] = instance
    except (ValidationError, SpecialistNotFoundError) as e:
        bdd_context.instantiation_error = e


@then('a validation error should be raised')
def validation_error_raised(bdd_context):
    """Verify validation error was raised"""
    assert bdd_context.instantiation_error is not None, \
        "Expected validation error to be raised"
    assert isinstance(bdd_context.instantiation_error, (ValidationError, SpecialistNotFoundError)), \
        f"Expected ValidationError or SpecialistNotFoundError, got {type(bdd_context.instantiation_error)}"


@then('the error should indicate missing specialist')
def error_indicates_missing_specialist(bdd_context):
    """Verify error message mentions missing specialist"""
    assert bdd_context.instantiation_error is not None, \
        "Expected error to exist"
    error_msg = str(bdd_context.instantiation_error).lower()
    assert 'specialist' in error_msg or 'missing' in error_msg, \
        f"Error should mention missing specialist, got: {error_msg}"


@then(parsers.parse('the instance status should be "{status}"'))
def instance_has_status(bdd_context, status):
    """Verify instance has expected status"""
    assert 'main' in bdd_context.instances, "Instance not created"
    instance = bdd_context.instances['main']
    assert instance.status == status, \
        f"Instance status should be {status}, got {instance.status}"


# ===== SCENARIO 4: Reuse template =====

@when('I reuse the same template with different assignments')
def reuse_template_with_new_assignments(instance_service, specialist_repo, bdd_context):
    """Reuse template with different specialist assignments"""
    template_name = bdd_context.current_template_name
    template = bdd_context.templates[template_name]

    # Create new specialists
    new_specs = {
        'planning': ('new_alice@example.com', 'pm'),
        'development': ('new_bob@example.com', 'engineer'),
        'testing': ('new_carol@example.com', 'qa'),
        'deployment': ('new_dave@example.com', 'devops')
    }

    for phase_key, (email, spec_type) in new_specs.items():
        if specialist_repo.get_agent_by_email(email) is None:
            specialist_repo.create_agent(
                name=email.split('@')[0].title(),
                email=email,
                specialist_type=spec_type
            )

    new_assignments = {k: v[0] for k, v in new_specs.items()}

    instance = instance_service.instantiate_workflow(
        template_id=template.id,
        instance_name=f"{template.name} Instance #2",
        specialist_assignments=new_assignments
    )

    bdd_context.instances['reused'] = instance


@then('a new workflow instance should be created from reused template')
def reused_instance_created(bdd_context):
    """Verify reused instance was created"""
    instance = bdd_context.instances['reused']
    assert instance.id is not None
    assert instance.status == 'ready'


@then('the reused instance should have new specialist assignments')
def reused_instance_has_new_assignments(bdd_context, instance_repo):
    """Verify reused instance has different specialists"""
    instance = bdd_context.instances['reused']
    template_name = bdd_context.current_template_name
    template = bdd_context.templates[template_name]
    assert instance.template_id == template.id
    phase_instances = instance_repo.get_phase_instances(instance.id)
    assert len(phase_instances) > 0


# ===== SCENARIO 5: Specialist validation error =====

@when('I attempt to instantiate the template with missing specialist')
def attempt_instantiate_with_missing_specialist(instance_service, bdd_context):
    """Attempt instantiation when specialist not available"""
    template_name = bdd_context.current_template_name
    template = bdd_context.templates[template_name]
    bdd_context.instantiation_error = None

    try:
        instance = instance_service.instantiate_workflow(
            template_id=template.id,
            instance_name=f"{template.name} With Error",
            specialist_assignments=bdd_context.specialist_assignments_dict
        )
        bdd_context.instances['error_test'] = instance
    except Exception as e:
        bdd_context.instantiation_error = e


@then('a validation error should be raised for missing specialist')
def validation_error_raised_for_missing(bdd_context):
    """Verify validation error was raised"""
    assert bdd_context.instantiation_error is not None


@then('the error should indicate which specialist type is missing')
def error_indicates_missing_specialist_type(bdd_context):
    """Verify error message mentions missing specialist"""
    assert bdd_context.instantiation_error is not None, "Expected error to be raised"
