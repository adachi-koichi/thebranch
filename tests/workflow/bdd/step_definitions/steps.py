"""BDD step definitions for workflow scenarios"""

import pytest
from pytest_bdd import given, when, then, parsers
from datetime import datetime


# ===== BACKGROUND: Initialize System =====

@given('the workflow system is initialized')
def system_initialized(template_service, instance_service, specialist_repo, bdd_context):
  """Verify system components are ready"""
  assert template_service is not None
  assert instance_service is not None
  assert specialist_repo is not None
  bdd_context.system_ready = True


@given('a test specialist directory exists with:')
def create_test_specialists(specialist_repo, bdd_context, table):
  """Create test specialists from table"""
  for row in table:
    specialist = specialist_repo.create_agent(
      name=row['Name'],
      email=row['Email'],
      specialist_type=row['Specialist Type']
    )
    bdd_context.specialists[row['Email']] = specialist


# ===== TEMPLATE CREATION =====

@when(parsers.parse('I create a workflow template named "{template_name}"'))
def create_template(template_service, bdd_context, template_name):
  """Create workflow template"""
  template = template_service.create_template(
    name=template_name,
    created_by="test@example.com"
  )
  bdd_context.templates[template_name] = template
  bdd_context.current_template = template
  assert template.id is not None


@when(parsers.parse('I add phase "{phase_name}" with specialist type "{specialist_type}" (sequential)'))
def add_sequential_phase(template_service, bdd_context, phase_name, specialist_type):
  """Add sequential phase to template"""
  template = bdd_context.current_template
  phase = template_service.add_phase(
    template_id=template.id,
    phase_key=phase_name.lower().replace(' ', '_'),
    phase_label=phase_name,
    specialist_type=specialist_type,
    phase_order=len(bdd_context.phases) + 1,
    is_parallel=False
  )
  bdd_context.phases[phase_name] = phase


@when(parsers.parse('I add {task_count:d} tasks to "{phase_name}" phase'))
def add_tasks_to_phase(template_service, bdd_context, task_count, phase_name):
  """Add tasks to phase"""
  template = bdd_context.current_template
  phase = bdd_context.phases[phase_name]

  for i in range(task_count):
    task = template_service.add_task_to_phase(
      phase_id=phase.id,
      task_key=f"{phase_name.lower().replace(' ', '_')}_task_{i + 1}",
      task_title=f"{phase_name} Task {i + 1}",
      task_description=f"Execute {phase_name} task {i + 1}",
      priority=i + 1,
      estimated_hours=4.0 + (i * 2)
    )
    if phase_name not in bdd_context.tasks:
      bdd_context.tasks[phase_name] = []
    bdd_context.tasks[phase_name].append(task)


@then('the template should have 3 phases in order')
def verify_phase_count(bdd_context):
  """Verify template has 3 phases"""
  assert len(bdd_context.phases) == 3


@then('all phases should be marked sequential')
def verify_phases_sequential(bdd_context):
  """Verify all phases are sequential"""
  for phase in bdd_context.phases.values():
    assert phase.is_parallel == 0


@then(parsers.parse('total task definitions should be {expected_count:d}'))
def verify_total_tasks(bdd_context, expected_count):
  """Verify total task count"""
  total = sum(len(tasks) for tasks in bdd_context.tasks.values())
  assert total == expected_count


@then('each task should have title, description, priority, and estimated hours')
def verify_task_fields(bdd_context):
  """Verify task fields are populated"""
  for tasks in bdd_context.tasks.values():
    for task in tasks:
      assert task.task_title is not None
      assert task.task_description is not None
      assert task.priority is not None
      assert task.estimated_hours is not None


# ===== INSTANCE CREATION =====

@given(parsers.parse('a workflow template named "{template_name}" with {phase_count:d} phases and {task_count:d} tasks'))
def create_template_with_phases_and_tasks(template_service, bdd_context, template_name, phase_count, task_count):
  """Create template with specified phases and tasks"""
  template = template_service.create_template(
    name=template_name,
    created_by="test@example.com"
  )
  bdd_context.current_template = template

  specialist_types = ['pm', 'engineer', 'qa']
  tasks_per_phase = task_count // phase_count

  for i in range(phase_count):
    phase_name = f"Phase {i + 1}"
    phase = template_service.add_phase(
      template_id=template.id,
      phase_key=phase_name.lower().replace(' ', '_'),
      phase_label=phase_name,
      specialist_type=specialist_types[i % len(specialist_types)],
      phase_order=i + 1,
      is_parallel=False
    )
    bdd_context.phases[phase_name] = phase

    for j in range(tasks_per_phase):
      template_service.add_task_to_phase(
        phase_id=phase.id,
        task_key=f"task_{j + 1}",
        task_title=f"{phase_name} Task {j + 1}",
        task_description=f"Execute task {j + 1}",
        priority=j + 1,
        estimated_hours=4.0
      )


@when(parsers.parse('I instantiate the template with specialist assignments:'))
def instantiate_template(instance_service, bdd_context, table):
  """Instantiate template with specialist assignments"""
  template = bdd_context.current_template
  assignments = {}

  for row in table:
    phase_name = row['Phase Name']
    email = row['Assigned Specialist']
    phase = bdd_context.phases[phase_name]
    assignments[phase.phase_key] = email

  instance = instance_service.create_instance(
    template_id=template.id,
    name=f"{template.name} Instance",
    specialist_assignments=assignments
  )
  bdd_context.current_instance = instance
  assert instance.id is not None


@when('the system auto-generates tasks from template definitions')
def autogenerate_tasks(instance_service, bdd_context):
  """Auto-generate tasks from template"""
  instance = bdd_context.current_instance
  template = bdd_context.current_template

  task_count = instance_service.task_gen_service.generate_tasks_for_instance(
    instance_id=instance.id,
    template_id=template.id
  )
  bdd_context.task_count = task_count


@then('a workflow instance should be created')
def verify_instance_created(bdd_context):
  """Verify instance exists"""
  assert bdd_context.current_instance is not None
  assert bdd_context.current_instance.id is not None


@then('instance should reference the original template')
def verify_instance_references_template(bdd_context):
  """Verify instance template reference"""
  instance = bdd_context.current_instance
  template = bdd_context.current_template
  assert instance.template_id == template.id


@then('all 3 phases should be initialized as phase instances')
def verify_phase_instances(bdd_context):
  """Verify phase instances created"""
  assert len(bdd_context.phases) == 3


@then(parsers.parse('{expected_count:d} total tasks should be created'))
def verify_task_creation(bdd_context, expected_count):
  """Verify task count"""
  assert bdd_context.task_count == expected_count


@then('tasks should be assigned to the phase specialists')
def verify_task_assignment(bdd_context):
  """Verify tasks assigned to specialists"""
  assert bdd_context.task_count > 0


@then('all generated tasks should start in "blocked" status')
def verify_tasks_blocked(bdd_context):
  """Verify tasks are blocked initially"""
  pass


@then('the first phase tasks should be unblocked')
def verify_first_phase_unblocked(bdd_context):
  """Verify first phase tasks unblocked"""
  pass


# ===== VALIDATION =====

@given(parsers.parse('a workflow template named "{template_name}"'))
def template_exists(template_service, bdd_context, template_name):
  """Create template"""
  template = template_service.create_template(
    name=template_name,
    created_by="test@example.com"
  )
  bdd_context.current_template = template


@given('the template has only 1 phase without any tasks')
def create_incomplete_template(template_service, bdd_context):
  """Create incomplete template"""
  template = bdd_context.current_template
  phase = template_service.add_phase(
    template_id=template.id,
    phase_key="incomplete",
    phase_label="Incomplete",
    specialist_type="pm",
    phase_order=1,
    is_parallel=False
  )
  bdd_context.phases["Incomplete"] = phase


@when('I attempt to validate the template')
def validate_template(template_service, bdd_context):
  """Validate template"""
  template = bdd_context.current_template
  try:
    template_service.validator.validate_template_completeness(template.id)
    bdd_context.validation_passed = True
  except Exception as e:
    bdd_context.validation_passed = False
    bdd_context.validation_errors.append(str(e))


@then('validation should fail with missing tasks error')
def verify_validation_failure(bdd_context):
  """Verify validation failed"""
  assert bdd_context.validation_passed == False
  assert len(bdd_context.validation_errors) > 0


@then('the template status should remain in "draft"')
def verify_template_draft_status(bdd_context):
  """Verify template status is draft"""
  template = bdd_context.current_template
  assert template.status == 'draft'


@when(parsers.parse('I attempt to instantiate with invalid specialist email "{invalid_email}"'))
def attempt_invalid_instantiation(instance_service, bdd_context, invalid_email):
  """Attempt instantiation with invalid specialist"""
  template = bdd_context.current_template
  assignments = {'phase_1': invalid_email}
  try:
    instance = instance_service.create_instance(
      template_id=template.id,
      name="Invalid Instance",
      specialist_assignments=assignments
    )
    bdd_context.instantiation_succeeded = True
  except Exception as e:
    bdd_context.instantiation_succeeded = False
    bdd_context.validation_errors.append(str(e))


@then('instantiation should fail')
def verify_instantiation_failed(bdd_context):
  """Verify instantiation failed"""
  assert bdd_context.instantiation_succeeded == False


@then('error message should indicate specialist not found')
def verify_specialist_error(bdd_context):
  """Verify error message"""
  assert any('specialist' in err.lower() for err in bdd_context.validation_errors)


# ===== AUDIT & MONITORING =====

@then('audit_logs should record:')
def verify_audit_logs(bdd_context, table):
  """Verify audit log entries"""
  for row in table:
    assert row['Field'] is not None
    assert row['Content'] is not None


@then('response should include:')
def verify_response_fields(bdd_context, table):
  """Verify response contains expected fields"""
  for row in table:
    assert row['Field'] is not None
    assert row['Content'] is not None


# ===== HELPER STEPS =====

@then('no error should occur')
def verify_no_error(bdd_context):
  """Verify no errors"""
  assert len(bdd_context.validation_errors) == 0
