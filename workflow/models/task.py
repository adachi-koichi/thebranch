from dataclasses import dataclass
from datetime import datetime


@dataclass
class TaskDependency:
    """Dependency edge in task DAG"""
    predecessor_id: int
    successor_id: int
    dep_type: str
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class DevTask:
    """Development task (extended)"""
    title: str
    assignee: str
    phase: str
    workflow_instance_id: int
    id: int | None = None
    description: str | None = None
    wf_node_key: str | None = None
    status: str = 'blocked'
    priority: int = 1
    estimated_hours: float | None = None
    version: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    unblocked_at: datetime | None = None
