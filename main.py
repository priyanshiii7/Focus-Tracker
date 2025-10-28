from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from datetime import datetime
from bson import ObjectId
import threading
import time

from models import *
from database import *
from cv_processor import CVProcessor

app = FastAPI(title="Focus Tracker API")

# Global state
current_session = None
current_user = None
cv_processor = None
session_start_time = None
current_intervals = []

def status_change_callback(new_status):
    """Called when CV detects status change"""
    global current_intervals, current_session
    
    if current_session:
        now = datetime.utcnow()
        
        # End previous interval
        if current_intervals:
            current_intervals[-1]["end"] = now.strftime("%H:%M:%S")
        
        # Start new interval
        current_intervals.append({
            "start": now.strftime("%H:%M:%S"),
            "end": None,
            "status": new_status
        })
        
        # Update session in DB
        update_session(current_session, {
            "focus_intervals": current_intervals
        })

@app.post("/session/start")
async def start_session(data: SessionStart):
    """Start a new focus session"""
    global current_session, current_user, cv_processor, session_start_time, current_intervals
    
    # Get or create user
    user = get_or_create_user(data.user_name)
    current_user = user
    
    # Create new session
    session_id = create_session(user["_id"], {})
    current_session = session_id
    session_start_time = datetime.utcnow()
    current_intervals = [{
        "start": session_start_time.strftime("%H:%M:%S"),
        "end": None,
        "status": "focused"
    }]
    
    # Start CV processor in background thread
    cv_processor = CVProcessor(callback=status_change_callback)
    cv_thread = threading.Thread(target=cv_processor.start, daemon=True)
    cv_thread.start()
    
    return {
        "message": "Session started",
        "session_id": str(session_id),
        "user_name": data.user_name
    }

@app.get("/session/current")
async def get_current_session_stats():
    """Get current session statistics"""
    global current_session, current_intervals, session_start_time
    
    if not current_session:
        raise HTTPException(status_code=404, detail="No active session")
    
    # Calculate metrics
    focus_time = 0
    break_time = 0
    away_time = 0
    phone_count = 0
    
    for interval in current_intervals:
        if interval["end"]:
            start = datetime.strptime(interval["start"], "%H:%M:%S")
            end = datetime.strptime(interval["end"], "%H:%M:%S")
            duration = (end - start).seconds
        else:
            # Current interval
            start = datetime.strptime(interval["start"], "%H:%M:%S")
            now = datetime.utcnow()
            duration = (now - now.replace(hour=start.hour, minute=start.minute, second=start.second)).seconds
        
        if interval["status"] == "focused":
            focus_time += duration
        elif interval["status"] == "away":
            away_time += duration
        elif interval["status"] == "phone_detected":
            phone_count += 1
            away_time += duration
    
    total_time = focus_time + away_time
    focus_score = (focus_time / total_time * 100) if total_time > 0 else 0
    
    metrics = {
        "focus_time": focus_time,
        "break_time": break_time,
        "away_time": away_time,
        "phone_detections": phone_count,
        "focus_score": round(focus_score, 1)
    }
    
    return {
        "session_id": str(current_session),
        "start_time": session_start_time,
        "current_status": cv_processor.get_current_status() if cv_processor else "unknown",
        "metrics": metrics,
        "is_active": True,
        "intervals": current_intervals
    }

@app.post("/session/end")
async def end_session():
    """End the current session"""
    global current_session, cv_processor, current_intervals
    
    if not current_session:
        raise HTTPException(status_code=404, detail="No active session")
    
    # Get final metrics
    stats = await get_current_session_stats()
    
    # Stop CV processor
    if cv_processor:
        cv_processor.stop()
        cv_processor = None
    
    # End current interval
    if current_intervals:
        current_intervals[-1]["end"] = datetime.utcnow().strftime("%H:%M:%S")
    
    # Update session in DB
    end_session(current_session, stats["metrics"])
    
    session_id = current_session
    current_session = None
    current_intervals = []
    
    return {
        "message": "Session ended",
        "session_id": str(session_id),
        "final_stats": stats["metrics"]
    }

@app.get("/sessions/today")
async def get_today_sessions():
    """Get all sessions from today"""
    if not current_user:
        raise HTTPException(status_code=404, detail="No active user")
    
    sessions = get_today_sessions(current_user["_id"])
    
    # Convert ObjectId to string for JSON serialization
    for session in sessions:
        session["_id"] = str(session["_id"])
        session["user_id"] = str(session["user_id"])
    
    return {"sessions": sessions}

@app.get("/analytics")
async def get_analytics():
    """Get aggregated analytics"""
    if not current_user:
        raise HTTPException(status_code=404, detail="No active user")
    
    sessions = get_today_sessions(current_user["_id"])
    
    total_focus = sum(s.get("metrics", {}).get("focus_time", 0) for s in sessions)
    total_sessions = len(sessions)
    avg_score = sum(s.get("metrics", {}).get("focus_score", 0) for s in sessions) / total_sessions if total_sessions > 0 else 0
    
    return {
        "today": {
            "total_focus_time": total_focus,
            "total_focus_hours": round(total_focus / 3600, 2),
            "sessions_count": total_sessions,
            "avg_focus_score": round(avg_score, 1)
        }
    }

# Serve static files
@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the dashboard"""
    try:
        with open("static/index.html", "r") as f:
            return f.read()
    except:
        return "<h1>Focus Tracker API</h1><p>Create static/index.html for the dashboard</p>"

if __name__ == "__main__":
    print("🎯 Starting Focus Tracker...")
    print("📊 Dashboard: http://localhost:8000")
    print("📝 API Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)