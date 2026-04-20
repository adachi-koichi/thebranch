from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InstanceSpecialist:
    """Specialist assignment for phase in workflow instance"""
    instance_id: int
    phase_id: int
    phase_key: str
    specialist_id: int
    specialist_slug: str
    specialist_name: str
    specialist_role: str
    id: int | None = None
    assigned_at: datetime | None = None


@dataclass
class InstanceNode:
    """Phase execution node within workflow instance"""
    instance_id: int
    phase_id: int
    phase_key: str
    status: str = 'waiting'
    id: int | None = None
    node_key: str | None = None
    node_type: str = 'task'
    task_id: int | None = None
    task_ids: list[int] | None = None
    result: str | None = None
    notes: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class PhaseInstance:
    """Phase instance within workflow instance (legacy alias for InstanceNode)"""
    phase_key: str
    id: int | None = None
    instance_id: int | None = None
    phase_id: int | None = None
    status: str = 'waiting'
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


@dataclass
class WorkflowInstance:
    """Instance of a workflow template"""
    template_id: int
    name: str
    id: int | None = None
    status: str = 'pending'
    context: dict[str, Any] | None = None
    current_phase_key: str | None = None
    project: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None
