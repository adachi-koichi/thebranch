from pydantic import BaseModel
from typing import Optional, List


class RiskDetection(BaseModel):
    risk_type: str
    severity: str
    ai_confidence_score: float
    description: Optional[str] = None


class RiskAlert(BaseModel):
    id: int
    sprint_id: int
    risk_type: str
    alert_message: str
    alert_level: str
    triggered_at: str
    resolved_at: Optional[str] = None
    resolution_note: Optional[str] = None
    created_at: str


class RiskAlertResolve(BaseModel):
    resolution_note: Optional[str] = None


class SeverityCount(BaseModel):
    critical: int
    high: int
    medium: int
    low: int


class RiskSummary(BaseModel):
    sprint_id: int
    total_risks_detected: int
    severity_breakdown: SeverityCount
    active_alerts: int
    resolved_alerts: int
    risk_trend: str
    top_risks: List[RiskDetection]
