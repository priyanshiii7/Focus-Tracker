from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, FileResponse, Response
import uvicorn
from datetime import datetime, timedelta
from bson import ObjectId
import threading
import time
import os
import shutil
import hashlib
import secrets
from typing import Optional
from fastapi import Body
from models import *
from database import *
import re
import cv2
from cv_processor import CVProcessor

app = FastAPI(title="Focus Tracker API")

# Create necessary directories
os.makedirs("static/uploads", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Session storage
active_sessions = {}

# Global state per user
user_sessions = {}
session_lock = threading.Lock()

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_session_token() -> str:
    """Create a secure session token"""
    return secrets.token_urlsafe(32)

def get_current_user(session_token: Optional[str] = Cookie(None)):
    """Get current user from session token"""
    if not session_token or session_token not in active_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return active_sessions[session_token]

# ==================== SESSION PERSISTENCE ====================

def save_session_to_db(user_id: str):
    """Save active session state to database"""
    try:
        if user_id not in user_sessions:
            return
        
        session_data = user_sessions[user_id]
        session_id = session_data.get("session_id")
        
        if not session_id:
            return
        
        metrics = calculate_current_metrics(session_data)
        
        sessions_collection.update_one(
            {"_id": session_id},
            {
                "$set": {
                    "focus_intervals": session_data["intervals"],
                    "recent_alerts": session_data.get("recent_alerts", []),
                    "metrics": metrics,
                    "last_updated": datetime.utcnow()
                }
            }
        )
        
        print(f"💾 Session persisted for user {user_id}")
        
    except Exception as e:
        print(f"⚠️  Error saving session to DB: {e}")

def restore_session_from_db(user_id: str):
    """Restore active session from database if it exists"""
    try:
        session = sessions_collection.find_one({
            "user_id": ObjectId(user_id),
            "end_time": None,
            "last_updated": {"$gte": datetime.utcnow() - timedelta(hours=2)}
        })
        
        if not session:
            return None
        
        print(f"🔄 Restoring session for user {user_id}")
        
        return {
            "session_id": session["_id"],
            "start_time": session["start_time"],
            "timer_end_time": session.get("timer_end_time"),
            "intervals": session.get("focus_intervals", []),
            "recent_alerts": session.get("recent_alerts", []),
            "metrics": session.get("metrics", {
                "studying_time": 0,
                "distracted_time": 0,
                "away_time": 0,
                "total_alerts": 0
            })
        }
        
    except Exception as e:
        print(f"⚠️  Error restoring session: {e}")
        return None

def calculate_current_metrics(session_data):
    """Calculate metrics from intervals with ongoing interval support"""
    metrics = {
        "studying_time": 0,
        "distracted_time": 0,
        "away_time": 0,
        "total_alerts": len(session_data.get("recent_alerts", [])),
        "focus_score": 0
    }
    
    now = datetime.utcnow()
    
    for interval in session_data.get("intervals", []):
        if interval.get("end"):
            end_time = datetime.fromisoformat(interval["end"])
        else:
            end_time = now
        
        start_time = datetime.fromisoformat(interval["start"])
        duration = (end_time - start_time).total_seconds()
        
        status = interval.get("status", "studying")
        if status == "studying":
            metrics["studying_time"] += duration
        elif status == "away":
            metrics["away_time"] += duration
        elif status == "distracted":
            metrics["distracted_time"] += duration
    
    total_time = metrics["studying_time"] + metrics["away_time"] + metrics["distracted_time"]
    if total_time > 0:
        metrics["focus_score"] = (metrics["studying_time"] / total_time) * 100
    else:
        metrics["focus_score"] = 100
    
    return metrics

def auto_save_sessions():
    """Background task to periodically save sessions"""
    while True:
        time.sleep(30)
        with session_lock:
            for user_id in list(user_sessions.keys()):
                save_session_to_db(user_id)

auto_save_thread = threading.Thread(target=auto_save_sessions, daemon=True)
auto_save_thread.start()
print("✅ Auto-save thread started")

# ==================== AUTHENTICATION ROUTES ====================

@app.get("/login", response_class=HTMLResponse)
async def login_page(session_token: Optional[str] = Cookie(None)):
    """Serve the login page"""
    if session_token and session_token in active_sessions:
        return RedirectResponse(url="/")
    
    try:
        with open("static/login.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error</h1><p>Login page not found: {str(e)}</p>"

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(session_token: Optional[str] = Cookie(None)):
    """Serve the signup page"""
    if session_token and session_token in active_sessions:
        return RedirectResponse(url="/")
    
    try:
        with open("static/signup.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error</h1><p>Signup page not found: {str(e)}</p>"

@app.post("/signup")
async def signup(
    name: str = Form(...), 
    email: str = Form(...), 
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Create new user account with validation"""
    if len(name.strip()) < 2:
        return HTMLResponse("""
            <html><body>
            <script>
                alert('Name must be at least 2 characters long');
                window.location.href = '/signup';
            </script>
            </body></html>
        """)
    
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return HTMLResponse("""
            <html><body>
            <script>
                alert('Invalid email format');
                window.location.href = '/signup';
            </script>
            </body></html>
        """)
    
    if len(password) < 8:
        return HTMLResponse("""
            <html><body>
            <script>
                alert('Password must be at least 8 characters long');
                window.location.href = '/signup';
            </script>
            </body></html>
        """)
    
    if password != confirm_password:
        return HTMLResponse("""
            <html><body>
            <script>
                alert('Passwords do not match');
                window.location.href = '/signup';
            </script>
            </body></html>
        """)
    
    existing_user = get_user_by_email(email)
    if existing_user:
        return HTMLResponse("""
            <html><body>
            <script>
                alert('Email already registered! Please login instead.');
                window.location.href = '/login';
            </script>
            </body></html>
        """)
    
    try:
        user = create_user(name.strip(), email.lower(), hash_password(password))
        
        session_token = create_session_token()
        active_sessions[session_token] = {
            "_id": user["_id"],
            "email": user["email"],
            "name": user["name"]
        }
        
        print(f"✅ New user registered: {name} ({email})")
        
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="session_token", value=session_token, httponly=True, max_age=86400*7)
        return response
    
    except Exception as e:
        print(f"❌ Signup error: {e}")
        return HTMLResponse("""
            <html><body>
            <script>
                alert('An error occurred during signup. Please try again.');
                window.location.href = '/signup';
            </script>
            </body></html>
        """)

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    """Login user with validation"""
    if not email or not password:
        return RedirectResponse(url="/login?error=Please enter both email and password", status_code=302)
    
    user = get_user_by_email(email.lower())
    
    if not user or user.get("password") != hash_password(password):
        return RedirectResponse(url="/login?error=Invalid email or password", status_code=302)
    
    update_last_login(user["_id"])
    
    session_token = create_session_token()
    active_sessions[session_token] = {
        "_id": user["_id"],
        "email": user["email"],
        "name": user["name"]
    }
    
    print(f"✅ User logged in: {user['name']} ({user['email']})")
    
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="session_token", value=session_token, httponly=True, max_age=86400*7)
    return response

@app.get("/logout")
async def logout(session_token: Optional[str] = Cookie(None)):
    """Logout user"""
    if session_token and session_token in active_sessions:
        user = active_sessions[session_token]
        user_id = str(user["_id"])
        
        if user_id in user_sessions:
            save_session_to_db(user_id)
        
        del active_sessions[session_token]
    
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="session_token")
    return response

@app.get("/api/current-user")
async def get_current_user_info(user = Depends(get_current_user)):
    """Get current logged in user info"""
    user_data = users_collection.find_one({"_id": user["_id"]})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "name": user_data["name"],
        "email": user_data["email"],
        "background_theme": user_data.get("background_theme", "gradient-purple"),
        "profile_picture": user_data.get("profile_picture"),
        "alert_preference": user_data.get("alert_preference", "both")
    }

# ==================== SESSION ROUTES ====================

@app.post("/session/start")
async def start_session(timer_duration: int = Body(None, embed=True), user = Depends(get_current_user)):
    """Start a new focus session with Python CV"""
    try:
        user_id = str(user["_id"])
        
        print(f"🔄 Starting session for user: {user['name']}")
        print(f"⏱️  Timer duration: {timer_duration} minutes")
        
        with session_lock:
            # Force clear any existing session
            if user_id in user_sessions:
                print(f"⚠️  Clearing existing session for user {user_id}")
                old_session = user_sessions[user_id]
                if old_session.get("cv_processor"):
                    try:
                        old_session["cv_processor"].stop()
                        time.sleep(0.5)
                    except:
                        pass
                save_session_to_db(user_id)
                del user_sessions[user_id]
            
            # Calculate timer end time
            timer_end_time = None
            if timer_duration:
                timer_end_time = datetime.utcnow() + timedelta(minutes=timer_duration)
            
            # Get user data
            user_data = users_collection.find_one({"_id": user["_id"]})
            if not user_data:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Create session in database
            session_doc = {
                "user_id": user["_id"],
                "start_time": datetime.utcnow(),
                "end_time": None,
                "timer_duration": timer_duration,
                "timer_end_time": timer_end_time,
                "focus_intervals": [],
                "recent_alerts": [],
                "metrics": {
                    "studying_time": 0,
                    "distracted_time": 0,
                    "away_time": 0,
                    "total_alerts": 0,
                    "focus_score": 100
                },
                "last_updated": datetime.utcnow()
            }
            
            result = sessions_collection.insert_one(session_doc)
            session_id = result.inserted_id
            print(f"💾 Session created in DB with ID: {session_id}")
            
            # Create session in memory
            session_start_time = datetime.utcnow()
            current_intervals = [{
                "start": session_start_time.isoformat(),
                "end": None,
                "status": "studying"
            }]
            
            user_sessions[user_id] = {
                "session_id": session_id,
                "cv_processor": None,
                "start_time": session_start_time,
                "timer_end_time": timer_end_time,
                "intervals": current_intervals,
                "recent_alerts": [],
                "metrics": {
                    "studying_time": 0,
                    "distracted_time": 0,
                    "away_time": 0,
                    "total_alerts": 0
                }
            }
        
        # Get alert preference
        alert_mode = user_data.get("alert_preference", "both")
        print(f"🔔 Alert mode: {alert_mode}")
        
        # Define status callback
        def status_callback(new_status, alert_data=None):
            try:
                with session_lock:
                    if user_id not in user_sessions:
                        return
                    
                    session_data = user_sessions[user_id]
                    
                    if new_status == "session_end":
                        return
                    
                    if alert_data:
                        session_data["recent_alerts"].append(alert_data)
                        session_data["metrics"]["total_alerts"] += 1
                        session_data["recent_alerts"] = session_data["recent_alerts"][-10:]
                    
                    now = datetime.utcnow()
                    if session_data["intervals"]:
                        session_data["intervals"][-1]["end"] = now.isoformat()
                    
                    session_data["intervals"].append({
                        "start": now.isoformat(),
                        "end": None,
                        "status": new_status
                    })
            except Exception as e:
                print(f"⚠️  Error in status callback: {e}")
        
        # Start CV processor
        print("📷 Starting CV processor...")
        cv_processor = CVProcessor(callback=status_callback, alert_mode=alert_mode)
        user_sessions[user_id]["cv_processor"] = cv_processor
        
        cv_thread = threading.Thread(target=cv_processor.start, daemon=True)
        cv_thread.start()
        
        print(f"✅ Session started successfully for {user['name']}")
        
        return {
            "message": "Session started",
            "session_id": str(session_id),
            "user_name": user["name"],
            "timer_end_time": timer_end_time.isoformat() if timer_end_time else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ FATAL ERROR starting session: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

@app.post("/session/end")
async def end_session_route(user = Depends(get_current_user)):
    """End the current session"""
    user_id = str(user["_id"])
    
    if user_id not in user_sessions:
        raise HTTPException(status_code=404, detail="No active session")
    
    session_data = user_sessions[user_id]
    
    print("🛑 Ending session...")
    
    # Get final stats
    try:
        stats = await get_current_session_stats(user)
    except Exception as e:
        print(f"⚠️  Error getting stats: {e}")
        stats = {
            "metrics": {
                "studying_time": 0,
                "distracted_time": 0,
                "away_time": 0,
                "total_alerts": 0,
                "focus_score": 0
            }
        }
    
    # Stop CV processor
    if session_data.get("cv_processor"):
        try:
            print("Stopping CV processor...")
            session_data["cv_processor"].stop()
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️  Error stopping CV processor: {e}")
    
    # Update session in database
    session_id = session_data["session_id"]
    
    with session_lock:
        try:
            if session_data["intervals"]:
                session_data["intervals"][-1]["end"] = datetime.utcnow().isoformat()
            
            sessions_collection.update_one(
                {"_id": session_id},
                {
                    "$set": {
                        "end_time": datetime.utcnow(),
                        "focus_intervals": session_data["intervals"],
                        "metrics": stats["metrics"]
                    }
                }
            )
            
            del user_sessions[user_id]
            
        except Exception as e:
            print(f"⚠️  Error updating session: {e}")
            if user_id in user_sessions:
                del user_sessions[user_id]
    
    print(f"✅ Session ended - Study time: {stats['metrics']['studying_time']}s")
    
    return {
        "message": "Session ended",
        "session_id": str(session_id),
        "final_stats": stats["metrics"]
    }

@app.get("/session/current")
async def get_current_session_stats(user = Depends(get_current_user)):
    """Get current session statistics"""
    user_id = str(user["_id"])
    
    if user_id not in user_sessions:
        raise HTTPException(status_code=404, detail="No active session")
    
    session_data = user_sessions[user_id]
    metrics = calculate_current_metrics(session_data)
    
    current_status = "studying"
    if session_data["intervals"]:
        current_status = session_data["intervals"][-1]["status"]
    
    return {
        "session_id": str(session_data["session_id"]),
        "start_time": session_data["start_time"].isoformat(),
        "current_status": current_status,
        "metrics": metrics,
        "recent_alerts": session_data.get("recent_alerts", []),
        "intervals": session_data.get("intervals", [])
    }

@app.get("/video_feed")
async def video_feed(user = Depends(get_current_user)):
    """Stream video feed from CV processor"""
    user_id = str(user["_id"])
    
    def generate_frames():
        if user_id not in user_sessions:
            return
        
        cv_processor = user_sessions[user_id].get("cv_processor")
        if not cv_processor:
            return
        
        frame_skip = 2
        frame_count = 0
        
        while cv_processor and cv_processor.is_running:
            frame_count += 1
            
            if frame_count % frame_skip != 0:
                time.sleep(0.01)
                continue
            
            frame = cv_processor.get_frame()
            
            if frame is not None:
                try:
                    # Resize for streaming
                    frame = cv2.resize(frame, (320, 240))
                    
                    # Add status overlay
                    status = cv_processor.get_current_status()
                    color = (0, 255, 0) if status == "studying" else (255, 140, 0)
                    cv2.putText(frame, f"Status: {status.upper()}", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    # Encode frame
                    ret, buffer = cv2.imencode('.jpg', frame, 
                        [cv2.IMWRITE_JPEG_QUALITY, 60])
                    
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                except:
                    pass
            
            time.sleep(0.1)
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# ==================== PROFILE & ANALYTICS ====================

@app.get("/user/profile")
async def get_user_profile(user = Depends(get_current_user)):
    """Get user profile"""
    user_data = users_collection.find_one({"_id": user["_id"]})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    stats = get_user_lifetime_stats(user["_id"])
    
    profile_picture = user_data.get("profile_picture")
    if profile_picture:
        profile_picture = f"{profile_picture}?t={int(datetime.utcnow().timestamp())}"
    
    return {
        "user_name": user_data["name"],
        "email": user_data["email"],
        "joined_date": user_data.get("created_at", datetime.utcnow()).isoformat(),
        "background_theme": user_data.get("background_theme", "gradient-purple"),
        "profile_picture": profile_picture,
        "alert_preference": user_data.get("alert_preference", "both"),
        "stats": stats
    }

@app.post("/user/profile")
async def update_user_profile_settings(profile: UserProfileUpdate, user = Depends(get_current_user)):
    """Update user profile settings"""
    updates = {}
    
    if profile.background_theme:
        updates["background_theme"] = profile.background_theme
    
    if hasattr(profile, 'new_name') and profile.new_name:
        existing_user = users_collection.find_one({
            "name": profile.new_name,
            "_id": {"$ne": user["_id"]}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")
        
        updates["name"] = profile.new_name
        
        for token, session in active_sessions.items():
            if session["_id"] == user["_id"]:
                session["name"] = profile.new_name
    
    users_collection.update_one({"_id": user["_id"]}, {"$set": updates})
    updated_user = users_collection.find_one({"_id": user["_id"]})
    
    return {
        "message": "Profile updated",
        "background_theme": updated_user.get("background_theme"),
        "user_name": updated_user.get("name")
    }

@app.get("/analytics/{period}")
async def get_analytics(period: str, user = Depends(get_current_user)):
    """Get analytics for day/week/month"""
    analytics = get_analytics_for_period(user["_id"], period)
    
    if "daily_breakdown" not in analytics:
        analytics["daily_breakdown"] = {}
    
    return {
        "period": period,
        "analytics": analytics
    }

# ==================== HTML ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def read_root(session_token: Optional[str] = Cookie(None)):
    """Serve the dashboard"""
    if not session_token or session_token not in active_sessions:
        return RedirectResponse(url="/login")
    
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>"

@app.get("/profile", response_class=HTMLResponse)
async def read_profile(session_token: Optional[str] = Cookie(None)):
    """Serve the profile page"""
    if not session_token or session_token not in active_sessions:
        return RedirectResponse(url="/login")
    
    profile_path = os.path.join("static", "profile.html")
    
    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"⚠️ Error reading profile.html: {e}")
    
    raise HTTPException(status_code=404, detail="Profile page not found")

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    for filename in ["favicon.ico", "favicon.png"]:
        favicon_path = os.path.join("static", filename)
        if os.path.exists(favicon_path):
            return FileResponse(favicon_path)
    return Response(status_code=204)

if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 8000))
    print("🎯 Starting Focus Tracker with Python CV Detection...")
    print("=" * 60)
    print(f"🚀 Server running on port {PORT}")
    print("📷 Using Python-based face detection (OpenCV + MediaPipe)")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=PORT)