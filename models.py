from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    name: str
    email: Optional[str] = None
    alert_preference: Optional[str] = "both"  # voice, text, both, none

class FocusInterval(BaseModel):
    start: str
    end: Optional[str] = None
    status: str  # "studying", "distracted", "away"

class SessionMetrics(BaseModel):
    studying_time: int = 0  # seconds
    distracted_time: int = 0
    away_time: int = 0
    total_alerts: int = 0
    focus_score: float = 0.0

class SessionStart(BaseModel):
    user_name: str

class SessionUpdate(BaseModel):
    status: str  # Current status: "studying", "distracted", "away"
    timestamp: Optional[datetime] = None

class AlertData(BaseModel):
    message: str
    timestamp: str
    type: str  # voice, text, both
    alert_level: str = "warning"  # warning, distraction

class SessionResponse(BaseModel):
    session_id: str
    user_name: str
    start_time: datetime
    current_status: str
    metrics: SessionMetrics
    is_active: bool
    recent_alerts: List[dict] = []
    intervals: List[dict] = []

class AnalyticsResponse(BaseModel):
    period: str
    total_studying_hours: float
    total_sessions: int
    focus_score: float
    total_alerts: int
    daily_breakdown: dict