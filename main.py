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

# Check if running on server
IS_SERVER = os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("DYNO")

# Get port from environment variable (for Render)
PORT = int(os.getenv("PORT", 8000))

if IS_SERVER:
    print("🌐 Running in SERVER mode - using browser-based face detection")
else:
    print("💻 Running in LOCAL mode - using Python CV")
    import cv2
    from cv_processor import CVProcessor

app = FastAPI(title="Focus Tracker API")

# Create necessary directories
os.makedirs("static/uploads", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Session storage (in production, use Redis)
active_sessions = {}

# Global state per user
user_sessions = {}
session_lock = threading.Lock()

# ==================== MAINTENANCE MODE ====================
MAINTENANCE_MODE = False  # Set to True to enable maintenance mode

def check_maintenance():
    """Check if maintenance mode is active"""
    if MAINTENANCE_MODE:
        raise HTTPException(
            status_code=503, 
            detail="System is under maintenance. Please try again later."
        )

@app.get("/api/maintenance")
async def get_maintenance_status():
    """Check maintenance mode status"""
    return {"maintenance_mode": MAINTENANCE_MODE}

@app.post("/api/admin/maintenance")
async def toggle_maintenance(enable: bool = Body(..., embed=True), admin_key: str = Body(..., embed=True)):
    """Toggle maintenance mode (admin only)"""
    ADMIN_KEY = os.getenv("ADMIN_KEY", "your-secret-admin-key-here")
    
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    global MAINTENANCE_MODE
    MAINTENANCE_MODE = enable
    
    return {
        "message": f"Maintenance mode {'enabled' if enable else 'disabled'}",
        "maintenance_mode": MAINTENANCE_MODE
    }

@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance_page():
    """Display maintenance page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Under Maintenance</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0;
            }
            .container {
                background: white;
                padding: 60px;
                border-radius: 20px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 500px;
            }
            h1 {
                color: #667eea;
                font-size: 3em;
                margin-bottom: 20px;
            }
            p {
                color: #718096;
                font-size: 1.2em;
                line-height: 1.6;
            }
            .emoji {
                font-size: 5em;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji">🔧</div>
            <h1>Under Maintenance</h1>
            <p>We're currently updating Focus Tracker to serve you better.</p>
            <p>We'll be back shortly. Thank you for your patience!</p>
        </div>
    </body>
    </html>
    """

# ==================== FAVICON ====================

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    for filename in ["favicon.ico", "favicon.png", "favicon.svg"]:
        favicon_path = os.path.join("static", filename)
        if os.path.exists(favicon_path):
            return FileResponse(favicon_path)
    return Response(status_code=204)

# ==================== AUTHENTICATION PAGE ROUTES ====================

@app.get("/login", response_class=HTMLResponse)
async def login_page(session_token: Optional[str] = Cookie(None)):
    """Serve the login page"""
    if MAINTENANCE_MODE:
        return RedirectResponse(url="/maintenance")
    
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
    if MAINTENANCE_MODE:
        return RedirectResponse(url="/maintenance")
    
    if session_token and session_token in active_sessions:
        return RedirectResponse(url="/")
    
    try:
        with open("static/signup.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error</h1><p>Signup page not found: {str(e)}</p>"

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
        # Use current time for ongoing intervals
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

# ==================== AUTHENTICATION ROUTES ====================

@app.post("/signup")
async def signup(
    name: str = Form(...), 
    email: str = Form(...), 
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Create new user account with validation"""
    check_maintenance()
    
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
    
    if not re.search(r'[A-Z]', password):
        return HTMLResponse("""
            <html><body>
            <script>
                alert('Password must contain at least one uppercase letter');
                window.location.href = '/signup';
            </script>
            </body></html>
        """)
    
    if not re.search(r'[a-z]', password):
        return HTMLResponse("""
            <html><body>
            <script>
                alert('Password must contain at least one lowercase letter');
                window.location.href = '/signup';
            </script>
            </body></html>
        """)
    
    if not re.search(r'[0-9]', password):
        return HTMLResponse("""
            <html><body>
            <script>
                alert('Password must contain at least one number');
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
    
    from database import get_user_by_email, create_user
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
    check_maintenance()
    
    if not email or not password:
        return RedirectResponse(url="/login?error=Please enter both email and password", status_code=302)
    
    from database import get_user_by_email, update_last_login
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
    
    user_id = str(user["_id"])
    restored_session = restore_session_from_db(user_id)
    if restored_session:
        print(f"🔄 Restored previous session for {user['name']}")
    
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
    check_maintenance()
    
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

# ==================== STATS ROUTES ====================

@app.get("/api/stats")
async def get_app_statistics():
    """Get application-wide statistics"""
    from database import get_app_stats, get_all_users_summary
    
    try:
        app_stats = get_app_stats()
        user_summary = get_all_users_summary()
        
        return {
            "success": True,
            "stats": {
                **app_stats,
                **user_summary
            }
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/stats", response_class=HTMLResponse)
async def stats_page():
    """Display application statistics page"""
    from database import get_app_stats, get_all_users_summary
    
    try:
        app_stats = get_app_stats()
        user_summary = get_all_users_summary()
        
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Focus Tracker Statistics</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='85' font-size='90'>📊</text></svg>">
    <style>
        body {{
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea, #764ba2);
            min-height: 100vh;
            padding: 40px 20px;
            margin: 0;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        h1 {{
            color: white;
            text-align: center;
            margin-bottom: 40px;
            font-size: 3em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 25px;
        }}
        .stat-card {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
        }}
        .stat-card h3 {{
            color: #667eea;
            font-size: 0.9em;
            text-transform: uppercase;
            margin-bottom: 15px;
            letter-spacing: 1px;
        }}
        .stat-card .value {{
            font-size: 3em;
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 10px;
        }}
        .stat-card .label {{
            color: #718096;
            font-size: 0.95em;
        }}
        .back-link {{
            display: block;
            text-align: center;
            margin-top: 40px;
            color: white;
            text-decoration: none;
            font-size: 1.1em;
            padding: 12px 30px;
            background: rgba(255,255,255,0.2);
            border-radius: 50px;
            display: inline-block;
            transition: all 0.3s;
        }}
        .back-link:hover {{
            background: white;
            color: #667eea;
        }}
        .center {{
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Focus Tracker Statistics</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Users</h3>
                <div class="value">{app_stats['total_users']}</div>
                <div class="label">registered accounts</div>
            </div>
            
            <div class="stat-card">
                <h3>New Today</h3>
                <div class="value">{user_summary['new_users_today']}</div>
                <div class="label">joined today</div>
            </div>
            
            <div class="stat-card">
                <h3>Active Users</h3>
                <div class="value">{user_summary['active_users_7_days']}</div>
                <div class="label">last 7 days</div>
            </div>
            
            <div class="stat-card">
                <h3>Total Sessions</h3>
                <div class="value">{app_stats['total_sessions']}</div>
                <div class="label">study sessions</div>
            </div>
            
            <div class="stat-card">
                <h3>Study Hours</h3>
                <div class="value">{app_stats['total_study_hours']}</div>
                <div class="label">total hours studied</div>
            </div>
            
            <div class="stat-card">
                <h3>Avg per User</h3>
                <div class="value">{round(app_stats['total_study_hours'] / max(app_stats['total_users'], 1), 1)}</div>
                <div class="label">hours per user</div>
            </div>
        </div>
        
        <div class="center">
            <a href="/" class="back-link">← Back to Dashboard</a>
        </div>
    </div>
</body>
</html>
        """
    except Exception as e:
        return f"""
        <html><body>
            <h1>Error loading statistics</h1>
            <p>{str(e)}</p>
            <a href="/">Back to home</a>
        </body></html>
        """

# ==================== SESSION ROUTES ====================

@app.post("/session/start")
async def start_session(timer_duration: int = Body(None, embed=True), user = Depends(get_current_user)):
    """Start a new focus session"""
    check_maintenance()
    
    try:
        user_id = str(user["_id"])
        
        print(f"🔄 Starting session for user: {user['name']}")
        print(f"⏱️  Timer duration: {timer_duration} minutes")
        
        with session_lock:
            # Force clear any existing session first
            if user_id in user_sessions:
                print(f"⚠️  Clearing existing session for user {user_id}")
                old_session = user_sessions[user_id]
                if not IS_SERVER and old_session.get("cv_processor"):
                    try:
                        old_session["cv_processor"].stop()
                        time.sleep(0.3)
                    except:
                        pass
                save_session_to_db(user_id)
                del user_sessions[user_id]
            
            # Calculate timer end time if provided
            timer_end_time = None
            if timer_duration:
                timer_end_time = datetime.utcnow() + timedelta(minutes=timer_duration)
                print(f"⏰ Timer will end at: {timer_end_time}")
            
            # Get user data
            user_data = users_collection.find_one({"_id": user["_id"]})
            if not user_data:
                print(f"❌ User not found: {user_id}")
                raise HTTPException(status_code=404, detail="User not found")
            
            print(f"✅ User data loaded: {user_data.get('name')}")
            
            # Create session in database
            from database import sessions_collection
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
            
            print(f"📝 Session stored in memory for user {user_id}")
        
        # Get alert preference
        alert_mode = user_data.get("alert_preference", "both")
        print(f"🔔 Alert mode: {alert_mode}")
        
        # Only start CV processor if NOT on server
        if not IS_SERVER:
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
        else:
            print("🌐 Browser mode: Face detection will run in browser")
        
        print(f"✅ Session started successfully for {user['name']}")
        
        return {
            "message": "Session started",
            "session_id": str(session_id),
            "user_name": user["name"],
            "timer_end_time": timer_end_time.isoformat() if timer_end_time else None,
            "browser_mode": IS_SERVER  # Tell frontend to handle detection
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ FATAL ERROR starting session: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@app.post("/session/status-update")
async def browser_status_update(
    status: str = Body(...),
    alert: dict = Body(None),
    user = Depends(get_current_user)
):
    """Receive status updates from browser-based face detection"""
    user_id = str(user["_id"])
    
    if user_id not in user_sessions:
        raise HTTPException(status_code=404, detail="No active session")
    
    with session_lock:
        session_data = user_sessions[user_id]
        now = datetime.utcnow()
        
        # Handle alert
        if alert:
            session_data["recent_alerts"].append(alert)
            session_data["metrics"]["total_alerts"] += 1
            session_data["recent_alerts"] = session_data["recent_alerts"][-10:]
        
        # Check if status actually changed
        current_intervals = session_data["intervals"]
        if current_intervals and current_intervals[-1]["status"] != status:
            # Close previous interval with exact timestamp
            current_intervals[-1]["end"] = now.isoformat()
            
            # Calculate duration and update metrics
            start_time = datetime.fromisoformat(current_intervals[-1]["start"])
            duration = (now - start_time).total_seconds()
            
            prev_status = current_intervals[-1]["status"]
            if prev_status == "studying":
                session_data["metrics"]["studying_time"] = session_data["metrics"].get("studying_time", 0) + duration
            elif prev_status == "away":
                session_data["metrics"]["away_time"] = session_data["metrics"].get("away_time", 0) + duration
            
            # Start new interval
            current_intervals.append({
                "start": now.isoformat(),
                "end": None,
                "status": status
            })
            
            print(f"🔄 Status changed: {prev_status} → {status} (duration: {duration:.1f}s)")
    
    return {"status": "updated"}


@app.post("/session/end")
async def end_session_route(user = Depends(get_current_user)):
    """End the current session"""
    user_id = str(user["_id"])
    
    if user_id not in user_sessions:
        raise HTTPException(status_code=404, detail="No active session")
    
    session_data = user_sessions[user_id]
    
    print("🛑 Ending session...")
    
    # Get final stats before stopping CV processor
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
    
    # Stop CV processor safely (only if not on server)
    if not IS_SERVER and session_data.get("cv_processor"):
        try:
            print("Stopping CV processor...")
            session_data["cv_processor"].stop()
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️  Error stopping CV processor: {e}")
    
    # Update session in database and clean up
    session_id = session_data["session_id"]
    
    with session_lock:
        try:
            # Close the last interval
            if session_data["intervals"]:
                session_data["intervals"][-1]["end"] = datetime.utcnow().isoformat()
            
            # Update session in database
            from database import sessions_collection
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
            
            # Remove from active sessions
            del user_sessions[user_id]
            
        except Exception as e:
            print(f"⚠️  Error updating session: {e}")
            # Still try to remove from memory
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
    """Get current session statistics with real-time accuracy"""
    user_id = str(user["_id"])
    
    if user_id not in user_sessions:
        raise HTTPException(status_code=404, detail="No active session")
    
    session_data = user_sessions[user_id]
    
    # Calculate metrics including the current ongoing interval
    metrics = {
        "studying_time": 0,
        "distracted_time": 0,
        "away_time": 0,
        "total_alerts": len(session_data.get("recent_alerts", [])),
        "focus_score": 0
    }
    
    now = datetime.utcnow()
    
    for interval in session_data.get("intervals", []):
        # Determine end time (use current time if interval is ongoing)
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
    
    # Calculate focus score
    total_time = metrics["studying_time"] + metrics["away_time"] + metrics["distracted_time"]
    if total_time > 0:
        metrics["focus_score"] = (metrics["studying_time"] / total_time) * 100
    else:
        metrics["focus_score"] = 100
    
    # Get current status from the last interval
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

@app.post("/session/force-clear")
async def force_clear_session(user = Depends(get_current_user)):
    """Force clear any stuck sessions for the user"""
    user_id = str(user["_id"])
    
    with session_lock:
        if user_id in user_sessions:
            session_data = user_sessions[user_id]
            
            # Save before clearing
            save_session_to_db(user_id)
            
            # Stop CV processor if exists (only if not on server)
            if not IS_SERVER and session_data.get("cv_processor"):
                try:
                    session_data["cv_processor"].stop()
                except:
                    pass
            
            del user_sessions[user_id]
            print(f"✅ Force cleared session for user {user_id}")
            
            return {"message": "Session cleared", "success": True}
        
        return {"message": "No session to clear", "success": False}

# ==================== SETTINGS ROUTES ====================

@app.post("/settings/alerts")
async def update_alert_settings(settings: dict, user = Depends(get_current_user)):
    """Update alert preferences"""
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"alert_preference": settings.get("alert_preference", "both")}}
    )
    
    # Update CV processor if session is active (only if not on server)
    if not IS_SERVER:
        user_id = str(user["_id"])
        if user_id in user_sessions:
            cv_processor = user_sessions[user_id].get("cv_processor")
            if cv_processor:
                cv_processor.set_alert_mode(settings.get("alert_preference", "both"))
    
    return {"message": "Settings updated"}

# ==================== ANALYTICS ROUTES ====================

@app.get("/analytics/{period}")
async def get_analytics(period: str, user = Depends(get_current_user)):
    """Get analytics for day/week/month with proper aggregation"""
    from database import get_analytics_for_period
    
    analytics = get_analytics_for_period(user["_id"], period)
    
    # Ensure all required fields are present
    if "daily_breakdown" not in analytics:
        analytics["daily_breakdown"] = {}
    
    return {
        "period": period,
        "analytics": analytics
    }
@app.post("/session/sync")
async def sync_session(user = Depends(get_current_user)):
    """Manually trigger session sync to database"""
    user_id = str(user["_id"])
    
    if user_id not in user_sessions:
        return {"message": "No active session", "success": False}
    
    try:
        save_session_to_db(user_id)
        return {"message": "Session synced", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


# ==================== PROFILE ROUTES ====================

@app.get("/user/profile")
async def get_user_profile(user = Depends(get_current_user)):
    """Get user profile with fresh data and cache busting"""
    from database import get_user_lifetime_stats
    
    user_data = users_collection.find_one({"_id": user["_id"]})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get fresh stats
    stats = get_user_lifetime_stats(user["_id"])
    
    # Add cache buster to profile picture URL
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
        "stats": stats,
        "timestamp": datetime.utcnow().isoformat()  # For cache busting
    }

@app.post("/user/profile")
async def update_user_profile_settings(profile: UserProfileUpdate, user = Depends(get_current_user)):
    """Update user profile settings"""
    updates = {}
    
    if profile.background_theme:
        updates["background_theme"] = profile.background_theme
    
    if hasattr(profile, 'new_name') and profile.new_name:
        # Check if new name already exists
        existing_user = users_collection.find_one({
            "name": profile.new_name,
            "_id": {"$ne": user["_id"]}
        })
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")
        
        updates["name"] = profile.new_name
        
        # Update session
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

@app.post("/user/profile/picture")
async def upload_profile_picture_endpoint(
    file: UploadFile = File(...),
    user = Depends(get_current_user)
):
    """Upload profile picture"""
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        file_extension = os.path.splitext(file.filename)[1]
        filename = f"{user['name']}_{int(time.time())}{file_extension}"
        file_path = os.path.join("static", "uploads", filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        url = f"/static/uploads/{filename}"
        users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"profile_picture": url}}
        )
        
        return {
            "message": "Profile picture uploaded",
            "url": url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to upload picture")

# ==================== VIDEO FEED ROUTE ====================

@app.get("/video_feed")
async def video_feed(user = Depends(get_current_user)):
    """Stream video feed (only works in local mode)"""
    if IS_SERVER:
        raise HTTPException(status_code=503, detail="Video feed not available in browser mode")
    
    user_id = str(user["_id"])
    
    def generate_frames():
        if user_id not in user_sessions:
            return
        
        cv_processor = user_sessions[user_id].get("cv_processor")
        if not cv_processor:
            return
        
        frame_skip = 4
        frame_count = 0
        
        while cv_processor and cv_processor.is_running:
            frame_count += 1
            
            if frame_count % frame_skip != 0:
                time.sleep(0.01)
                continue
            
            frame = cv_processor.get_frame()
            
            if frame is not None:
                try:
                    frame = cv2.resize(frame, (240, 180))
                    
                    status = cv_processor.get_current_status()
                    color = (0, 255, 0) if status == "studying" else (255, 140, 0)
                    cv2.putText(frame, status.upper(), (10, 25), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    ret, buffer = cv2.imencode('.jpg', frame, 
                        [cv2.IMWRITE_JPEG_QUALITY, 50,
                         cv2.IMWRITE_JPEG_OPTIMIZE, 1])
                    
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                except:
                    pass
            
            time.sleep(0.15)
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# ==================== HTML ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def read_root(session_token: Optional[str] = Cookie(None)):
    """Serve the dashboard or redirect to login"""
    if MAINTENANCE_MODE:
        return RedirectResponse(url="/maintenance")
    
    if not session_token or session_token not in active_sessions:
        return RedirectResponse(url="/login")
    
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>"

@app.get("/profile", response_class=HTMLResponse)
async def read_profile(session_token: Optional[str] = Cookie(None)):
    """Serve the profile page or redirect to login"""
    if MAINTENANCE_MODE:
        return RedirectResponse(url="/maintenance")
    
    if not session_token or session_token not in active_sessions:
        return RedirectResponse(url="/login")
    
    try:
        with open("static/profile.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>"

@app.get("/version")
async def get_version():
    """Get API version info"""
    return {
        "version": "2.0.0",
        "mode": "server" if IS_SERVER else "local",
        "updated": datetime.utcnow().isoformat(),
        "maintenance_mode": MAINTENANCE_MODE
    }

if __name__ == "__main__":
    print("🎯 Starting Enhanced Focus Tracker with Authentication...")
    print("=" * 60)
    print(f"🚀 Server running on port {PORT}")
    print(f"🎨 Mode: {'SERVER (Browser Detection)' if IS_SERVER else 'LOCAL (Python CV)'}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=PORT)