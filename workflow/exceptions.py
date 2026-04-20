"""
Workflow system exception hierarchy.

Custom exceptions for workflow template management, instantiation,
task generation, and specialist assignment.
"""

from typing import Any


class WorkflowException(Exception):
    """Base exception for workflow system"""
    pass


# ===== Template Exceptions =====

class TemplateException(WorkflowException):
    """Template-related errors"""
    pass


class TemplateNotFoundError(TemplateException):
    """Template not found by id"""
    pass


class ValidationError(TemplateException):
    """Validation failed (template, phase, task, assignment, etc)"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


class CircularDependencyError(TemplateException):
    """Circular dependency detected in task graph"""

    def __init__(self, cycle_path: list[int]):
        self.cycle_path = cycle_path
        cycle_str = ' → '.join(map(str, cycle_path))
        super().__init__(f"Circular dependency: {cycle_str}")


class PhaseException(TemplateException):
    """Phase-related errors"""
    pass


class PhaseNotFoundError(PhaseException):
    """Phase not found"""
    pass


# ===== Instance Exceptions =====

class InstanceException(WorkflowException):
    """Instance-related errors"""
    pass


class InstanceNotFoundError(InstanceException):
    """Workflow instance not found by id"""
    pass


class InvalidStateTransitionError(InstanceException):
    """Invalid state transition (e.g., running → waiting)"""
    pass


# ===== Assignment Exceptions =====

class AssignmentException(WorkflowException):
    """Assignment-related errors"""
    pass


class SpecialistNotFoundError(AssignmentException):
    """Specialist/agent not found"""
    pass


class SpecialistAssignmentError(AssignmentException):
    """Specialist assignment failed (type mismatch, not available, etc)"""
    pass


# ===== Database Exceptions =====

class DatabaseError(WorkflowException):
    """Database operation failed (SQLite or KuzuDB)"""
    pass
