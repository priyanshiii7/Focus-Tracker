from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn
from datetime import datetime, timedelta
from bson import ObjectId
import threading
import time
import cv2

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
recent_alerts = []
session_metrics = {
    "studying_time": 0,
    "distracted_time": 0,
    "away_time": 0,
    "total_alerts": 0
}

def status_change_callback(new_status, alert_data=None):
    """Called when CV detects status change or alert"""
    global current_intervals, current_session, recent_alerts, session_metrics
    
    # Handle session end request
    if new_status == "session_end":
        print(f"Session end requested: {alert_data['reason']}")
        return
    
    # Handle alert
    if alert_data:
        recent_alerts.append(alert_data)
        session_metrics["total_alerts"] += 1
        # Keep only last 10 alerts
        recent_alerts = recent_alerts[-10:]
    
    if current_session:
        now = datetime.utcnow()
        
        # End previous interval
        if current_intervals:
            current_intervals[-1]["end"] = now.isoformat()
        
        # Start new interval
        current_intervals.append({
            "start": now.isoformat(),
            "end": None,
            "status": new_status
        })
        
        # Update session in DB
        update_session(current_session, {
            "focus_intervals": current_intervals,
            "recent_alerts": recent_alerts
        })

@app.post("/session/start")
async def start_session(data: SessionStart):
    """Start a new focus session"""
    global current_session, current_user, cv_processor, session_start_time, current_intervals, recent_alerts, session_metrics
    
    # Get or create user
    user = get_or_create_user(data.user_name)
    current_user = user
    
    # Create new session
    session_id = create_session(user["_id"], {})
    current_session = session_id
    session_start_time = datetime.utcnow()
    current_intervals = [{
        "start": session_start_time.isoformat(),
        "end": None,
        "status": "studying"
    }]
    recent_alerts = []
    session_metrics = {
        "studying_time": 0,
        "distracted_time": 0,
        "away_time": 0,
        "total_alerts": 0
    }
    
    # Start CV processor in background thread
    alert_mode = user.get("alert_preference", "both")
    cv_processor = CVProcessor(callback=status_change_callback, alert_mode=alert_mode)
    cv_thread = threading.Thread(target=cv_processor.start, daemon=True)
    cv_thread.start()
    
    print(f"✅ Session started for {data.user_name}")
    
    return {
        "message": "Session started",
        "session_id": str(session_id),
        "user_name": data.user_name
    }

@app.get("/session/current")
async def get_current_session_stats():
    """Get current session statistics"""
    global current_session, current_intervals, session_start_time, session_metrics
    
    if not current_session:
        raise HTTPException(status_code=404, detail="No active session")
    
    # Calculate metrics from intervals
    studying_time = 0
    distracted_time = 0
    away_time = 0
    
    current_time = datetime.utcnow()
    
    for interval in current_intervals:
        try:
            start = datetime.fromisoformat(interval["start"])
            
            if interval["end"]:
                end = datetime.fromisoformat(interval["end"])
            else:
                # Current ongoing interval
                end = current_time
            
            duration = (end - start).total_seconds()
            
            if interval["status"] == "studying":
                studying_time += duration
            elif interval["status"] == "distracted":
                distracted_time += duration
            elif interval["status"] == "away":
                away_time += duration
        except Exception as e:
            print(f"Error processing interval: {e}")
            continue
    
    total_time = studying_time + distracted_time + away_time
    focus_score = (studying_time / total_time * 100) if total_time > 0 else 100
    
    metrics = {
        "studying_time": int(studying_time),
        "distracted_time": int(distracted_time),
        "away_time": int(away_time),
        "total_alerts": session_metrics["total_alerts"],
        "focus_score": round(focus_score, 1)
    }
    
    print(f"📊 Current stats: Study={int(studying_time)}s, Away={int(away_time)}s, Focus={focus_score:.1f}%")
    
    return {
        "session_id": str(current_session),
        "start_time": session_start_time.isoformat(),
        "current_status": cv_processor.get_current_status() if cv_processor else "unknown",
        "metrics": metrics,
        "is_active": True,
        "intervals": current_intervals,
        "recent_alerts": recent_alerts
    }

@app.post("/session/end")
async def end_session():
    """End the current session"""
    global current_session, cv_processor, current_intervals, session_metrics
    
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
        current_intervals[-1]["end"] = datetime.utcnow().isoformat()
    
    # Update session in DB with final metrics
    from database import end_session as db_end_session
    db_end_session(current_session, stats["metrics"])
    
    session_id = current_session
    current_session = None
    current_intervals = []
    
    print(f"✅ Session ended - Study time: {stats['metrics']['studying_time']}s")
    
    return {
        "message": "Session ended",
        "session_id": str(session_id),
        "final_stats": stats["metrics"]
    }

@app.post("/settings/alerts")
async def update_alert_settings(settings: dict):
    """Update alert preferences"""
    global current_user, cv_processor
    
    if current_user:
        users_collection.update_one(
            {"_id": current_user["_id"]},
            {"$set": {"alert_preference": settings.get("alert_preference", "both")}}
        )
        
        if cv_processor:
            cv_processor.set_alert_mode(settings.get("alert_preference", "both"))
    
    return {"message": "Settings updated"}

@app.get("/analytics/{period}")
async def get_analytics(period: str):
    """Get analytics for day/week/month"""
    global current_user
    
    if not current_user:
        raise HTTPException(status_code=404, detail="No active user")
    
    # Calculate date ranges
    now = datetime.utcnow()
    
    if period == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        raise HTTPException(status_code=400, detail="Invalid period")
    
    # Get sessions in date range
    sessions = list(sessions_collection.find({
        "user_id": current_user["_id"],
        "start_time": {"$gte": start_date}
    }))
    
    # Calculate totals
    total_studying = sum(s.get("metrics", {}).get("studying_time", 0) for s in sessions)
    total_away = sum(s.get("metrics", {}).get("away_time", 0) for s in sessions)
    total_distracted = sum(s.get("metrics", {}).get("distracted_time", 0) for s in sessions)
    total_alerts = sum(s.get("metrics", {}).get("total_alerts", 0) for s in sessions)
    
    total_time = total_studying + total_away + total_distracted
    focus_score = (total_studying / total_time * 100) if total_time > 0 else 0
    
    # Daily breakdown
    daily_breakdown = {}
    for session in sessions:
        date_key = session["start_time"].strftime("%Y-%m-%d")
        
        if date_key not in daily_breakdown:
            daily_breakdown[date_key] = {
                "studying": 0,
                "distracted": 0,  # This will include away time
                "sessions": 0
            }
        
        daily_breakdown[date_key]["studying"] += session.get("metrics", {}).get("studying_time", 0)
        # Combine away and distracted time
        daily_breakdown[date_key]["distracted"] += session.get("metrics", {}).get("away_time", 0)
        daily_breakdown[date_key]["distracted"] += session.get("metrics", {}).get("distracted_time", 0)
        daily_breakdown[date_key]["sessions"] += 1
    
    return {
        "period": period,
        "analytics": {
            "total_studying_hours": round(total_studying / 3600, 1),
            "total_sessions": len(sessions),
            "focus_score": round(focus_score, 1),
            "total_alerts": total_alerts,
            "daily_breakdown": daily_breakdown
        }
    }

def generate_frames():
    """Generate video frames for streaming"""
    global cv_processor
    
    print("📹 Video streaming started")
    frame_skip = 2  # Send every 2nd frame to reduce lag
    frame_count = 0
    
    while cv_processor and cv_processor.is_running:
        frame_count += 1
        
        # Skip frames to reduce lag
        if frame_count % frame_skip != 0:
            time.sleep(0.016)  # ~60 FPS capture but send less
            continue
        
        frame = cv_processor.get_frame()
        
        if frame is not None:
            try:
                # Resize for better streaming performance (smaller = faster)
                frame = cv2.resize(frame, (480, 360))
                
                # Add minimal status overlay
                status = cv_processor.get_current_status()
                color = (0, 255, 0) if status == "studying" else (0, 165, 255)
                cv2.putText(frame, status.upper(), (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                
                # Encode with lower quality for speed
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                print(f"Frame encoding error: {e}")
        
        time.sleep(0.05)  # ~20 FPS streaming (reduced from 30)
    
    print("📹 Video streaming stopped")

@app.get("/video_feed")
async def video_feed():
    """Stream video feed"""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the dashboard"""
    try:
        import os
        file_path = os.path.join("static", "index.html")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            return content
    except Exception as e:
        print(f"Error loading index.html: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p><p>Make sure static/index.html exists!</p>"

if __name__ == "__main__":
    print("🎯 Starting Enhanced Focus Tracker...")
    print("📊 Dashboard: http://localhost:8000")
    print("📝 API Docs: http://localhost:8000/docs")
    print("📹 Live feed enabled")
    uvicorn.run(app, host="0.0.0.0", port=8000)