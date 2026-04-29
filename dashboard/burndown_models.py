from pydantic import BaseModel
from typing import Optional, List


class BurndownProgressCreate(BaseModel):
    tracked_date: str
    completed_points: int
    remaining_points: Optional[int] = None


class BurndownPoint(BaseModel):
    date: str
    remaining_points: float


class BurndownSummary(BaseModel):
    sprint_id: int
    total_story_points: float
    completed_points: float
    remaining_points: float
    health_status: str
    sprint_start_date: str
    sprint_end_date: str
    actual_velocity: Optional[float] = None
    tracked_date: Optional[str] = None


class BurndownChartData(BaseModel):
    sprint_id: int
    sprint_name: str
    total_story_points: float
    actual_line: List[BurndownPoint]
    ideal_line: List[BurndownPoint]
    health_status: str
    days_remaining: int


class BurndownForecast(BaseModel):
    sprint_id: int
    current_velocity: float
    estimated_completion_date: Optional[str] = None
    expected_remaining_points: float
    on_track: bool
    days_remaining: int
