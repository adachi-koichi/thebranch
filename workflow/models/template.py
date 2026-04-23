from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskDef:
    """Task definition within a phase"""
    task_key: str
    task_title: str
    id: int | None = None
    phase_id: int | None = None
    template_id: int | None = None
    task_description: str | None = None
    category: str | None = None
    priority: int = 3
    estimated_hours: int | None = None
    depends_on_key: str | None = None
    task_order: int = 0
    acceptance_criteria: str | None = None
    tags: list[str] | None = None
    config: dict | None = None
    created_at: datetime | None = None


@dataclass
class Phase:
    """Phase definition within template"""
    phase_key: str
    phase_label: str
    specialist_type: str
    phase_order: int
    id: int | None = None
    template_id: int | None = None
    description: str | None = None
    specialist_count: int = 1
    is_parallel: bool = False
    task_count: int = 0
    estimated_hours: int | None = None
    config: dict | None = None
    tasks: list[TaskDef] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Template:
    """Workflow template (immutable after creation)"""
    name: str
    id: int | None = None
    description: str | None = None
    category: str | None = None
    version: int = 1
    status: str = 'draft'
    owner_id: int | None = None
    organization_id: int | None = None
    phase_count: int = 0
    task_count: int = 0
    estimated_hours: int | None = None
    tags: list[str] | None = None
    config: dict | None = None
    phases: list[Phase] | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ===== Template Catalog & Matching =====

@dataclass
class TemplateMetadata:
    """Template metadata for catalog"""
    template_id: int
    name: str
    description: str | None = None
    category: str | None = None
    usage_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class TemplateMatch:
    """Template matching result with score"""
    template_id: int
    name: str
    match_score: float  # 0.0 ~ 1.0
    match_reason: str
    matched_fields: list[str] = field(default_factory=list)


# ===== Exceptions =====

class TemplateNotFoundError(Exception):
    """Template not found"""
    pass


class TemplateValidationError(Exception):
    """Template validation error"""
    pass
