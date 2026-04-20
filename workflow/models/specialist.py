from dataclasses import dataclass
from datetime import datetime


@dataclass
class Agent:
    """Specialist / Agent"""
    name: str
    email: str
    specialist_type: str
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class SpecialistAssignment:
    """Assignment of specialist to phase within instance"""
    instance_id: int
    phase_id: int
    specialist_id: int
    specialist_slug: str
    specialist_name: str
    id: int | None = None
    created_at: datetime | None = None
