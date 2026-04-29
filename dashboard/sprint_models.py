from pydantic import BaseModel
from typing import Optional


class SprintCreate(BaseModel):
    department_id: int
    name: str
    sprint_start_date: str
    sprint_end_date: str
    target_velocity: float = 20


class SprintUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    target_velocity: Optional[float] = None


class SprintResponse(BaseModel):
    id: int
    department_id: int
    name: str
    status: str
    sprint_start_date: str
    sprint_end_date: str
    target_velocity: float
    actual_velocity: Optional[float] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SprintTaskCreate(BaseModel):
    task_key: str
    title: str
    story_points: int
    status: str = "todo"
    assigned_to: Optional[str] = None


class SprintTaskUpdate(BaseModel):
    title: Optional[str] = None
    story_points: Optional[int] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None


class SprintTaskResponse(BaseModel):
    id: int
    sprint_id: int
    task_key: str
    title: str
    story_points: int
    status: str
    assigned_to: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
