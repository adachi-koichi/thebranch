"""Business logic layer for workflow system

Services (5 modules):
- TemplateService: Template CRUD & lifecycle
- WorkflowInstanceService: Instance instantiation & execution
- TaskGenerationService: Auto-generate tasks & dependencies
- SpecialistAssignmentService: Agent assignment & validation
"""

from workflow.services.template import TemplateService
from workflow.services.instance import WorkflowInstanceService
from workflow.services.task_gen import TaskGenerationService
from workflow.services.assignment import SpecialistAssignmentService

__all__ = [
    'TemplateService',
    'WorkflowInstanceService',
    'TaskGenerationService',
    'SpecialistAssignmentService',
]
