from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    name: str
    email: Optional[str] = None

class FocusInterval(BaseModel):
    start: str
    end: Optional[str] = None
    status: str  # "focused", "away", "phone_detected", "break"

class SessionMetrics(BaseModel):
    focus_time: int = 0  # seconds
    break_time: int = 0
    away_time: int = 0
    phone_detections: int = 0
    focus_score: float = 0.0

class SessionStart(BaseModel):
    user_name: str

class SessionUpdate(BaseModel):
    status: str  # Current status: "focused", "away", "phone_detected"
    timestamp: Optional[datetime] = None

class SessionResponse(BaseModel):
    session_id: str
    user_name: str
    start_time: datetime
    current_status: str
    metrics: SessionMetrics
    is_active: bool