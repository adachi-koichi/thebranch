"""CLI service factory - DI pattern."""

import json
from typing import TYPE_CHECKING

from workflow.services.template import TemplateService
from workflow.services.instance import WorkflowInstanceService
from workflow.services.assignment import SpecialistAssignmentService
from workflow.services.task_gen import TaskGenerationService
from workflow.repositories.template import TemplateRepository
from workflow.repositories.instance import InstanceRepository
from workflow.repositories.task import TaskRepository
from workflow.repositories.specialist import SpecialistRepository
from workflow.validation.template import TemplateValidator
from workflow.validation.instance import InstanceValidator
from workflow.validation.assignment import AssignmentValidator
from workflow.validation.task import TaskValidator

if TYPE_CHECKING:
    from workflow.db import DatabaseConnection


class ServiceFactory:
    """Factory for service instances."""

    _instance = None
    _db_conn = None

    def __init__(self, db_connection: 'DatabaseConnection' | None = None) -> None:
        self.db_conn = db_connection or self._get_default_connection()
        self._services = {}

    @staticmethod
    def _get_default_connection():
        from workflow.db import get_connection
        return get_connection()

    def get_template_service(self) -> TemplateService:
        if 'template_service' not in self._services:
            repo = TemplateRepository(self.db_conn)
            validator = TemplateValidator(repo)
            self._services['template_service'] = TemplateService(repo, validator)
        return self._services['template_service']

    def get_instance_service(self) -> WorkflowInstanceService:
        if 'instance_service' not in self._services:
            instance_repo = InstanceRepository(self.db_conn)
            template_repo = TemplateRepository(self.db_conn)
            task_gen_svc = self.get_task_gen_service()
            assignment_svc = self.get_assignment_service()
            validator = InstanceValidator(instance_repo)
            self._services['instance_service'] = WorkflowInstanceService(
                instance_repo, template_repo, task_gen_svc, assignment_svc, validator
            )
        return self._services['instance_service']

    def get_assignment_service(self) -> SpecialistAssignmentService:
        if 'assignment_service' not in self._services:
            repo = SpecialistRepository(self.db_conn)
            validator = AssignmentValidator(repo)
            self._services['assignment_service'] = SpecialistAssignmentService(repo, validator)
        return self._services['assignment_service']

    def get_task_gen_service(self) -> TaskGenerationService:
        if 'task_gen_service' not in self._services:
            task_repo = TaskRepository(self.db_conn)
            template_repo = TemplateRepository(self.db_conn)
            instance_repo = InstanceRepository(self.db_conn)
            validator = TaskValidator(template_repo, instance_repo)
            self._services['task_gen_service'] = TaskGenerationService(
                task_repo, template_repo, instance_repo, validator
            )
        return self._services['task_gen_service']

    @classmethod
    def get_instance(cls) -> 'ServiceFactory':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def format_response(success: bool, data=None, error=None) -> dict:
    """Format CLI response as JSON."""
    response = {'success': success}
    if success and data is not None:
        response['data'] = data
    if not success and error is not None:
        response['error'] = error
    return response


def dataclass_to_dict(obj) -> dict:
    """Convert dataclass to dict for JSON serialization."""
    from dataclasses import asdict
    return asdict(obj)


def format_exception(exc: Exception) -> dict:
    """Format exception for JSON error response."""
    from workflow.exceptions import (
        TemplateNotFoundError,
        InstanceNotFoundError,
        SpecialistNotFoundError,
        ValidationError,
        CircularDependencyError,
    )

    error_type = exc.__class__.__name__
    message = str(exc)
    details = {}

    if isinstance(exc, ValidationError):
        details = getattr(exc, 'details', {})
    elif isinstance(exc, CircularDependencyError):
        details = {'cycle_path': getattr(exc, 'cycle_path', [])}

    return {
        'type': error_type,
        'message': message,
        'details': details,
    }
