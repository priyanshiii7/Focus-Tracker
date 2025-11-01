from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["focus_tracker"]

# Collections
users_collection = db["users"]
sessions_collection = db["sessions"]
app_stats_collection = db["app_stats"]  # New collection for app-wide statistics

# Create indexes
users_collection.create_index("email", unique=True)
users_collection.create_index("name")
sessions_collection.create_index("user_id")
sessions_collection.create_index("start_time")

def initialize_app_stats():
    """Initialize app statistics if not exists"""
    if not app_stats_collection.find_one({"_id": "global_stats"}):
        app_stats_collection.insert_one({
            "_id": "global_stats",
            "total_users": 0,
            "total_sessions": 0,
            "total_study_hours": 0,
            "created_at": datetime.utcnow(),
            "last_updated": datetime.utcnow()
        })
        print("✅ App statistics initialized")

# Initialize on import
initialize_app_stats()

def increment_user_count():
    """Increment total user count"""
    app_stats_collection.update_one(
        {"_id": "global_stats"},
        {
            "$inc": {"total_users": 1},
            "$set": {"last_updated": datetime.utcnow()}
        }
    )

def get_app_stats():
    """Get application-wide statistics"""
    stats = app_stats_collection.find_one({"_id": "global_stats"})
    if not stats:
        return {
            "total_users": 0,
            "total_sessions": 0,
            "total_study_hours": 0
        }
    return {
        "total_users": stats.get("total_users", 0),
        "total_sessions": stats.get("total_sessions", 0),
        "total_study_hours": round(stats.get("total_study_hours", 0), 1),
        "created_at": stats.get("created_at"),
        "last_updated": stats.get("last_updated")
    }

def create_user(name: str, email: str, password_hash: str):
    """Create a new user"""
    user = {
        "name": name,
        "email": email,
        "password": password_hash,
        "created_at": datetime.utcnow(),
        "total_sessions": 0,
        "total_focus_hours": 0.0,
        "background_theme": "gradient-purple",
        "profile_picture": None,
        "alert_preference": "both",
        "last_login": datetime.utcnow()
    }
    
    result = users_collection.insert_one(user)
    user["_id"] = result.inserted_id
    
    # Increment global user count
    increment_user_count()
    
    print(f"✅ New user created: {name} ({email})")
    return user

def update_last_login(user_id):
    """Update user's last login timestamp"""
    users_collection.update_one(
        {"_id": user_id},
        {"$set": {"last_login": datetime.utcnow()}}
    )

def get_user_by_email(email: str):
    """Get user by email"""
    return users_collection.find_one({"email": email})

def get_user_by_id(user_id):
    """Get user by ID"""
    return users_collection.find_one({"_id": user_id})

def get_or_create_user(name: str, email: str = None):
    """Get existing user or create new one (for backward compatibility)"""
    user = users_collection.find_one({"name": name})
    
    if not user:
        user = {
            "name": name,
            "email": email,
            "password": None,  # For users created without authentication
            "created_at": datetime.utcnow(),
            "total_sessions": 0,
            "total_focus_hours": 0.0,
            "background_theme": "gradient-purple",
            "profile_picture": None,
            "alert_preference": "both"
        }
        result = users_collection.insert_one(user)
        user["_id"] = result.inserted_id
    
    return user

def create_session(user_id, session_data: dict):
    """Create a new session"""
    session = {
        "user_id": user_id,
        "start_time": datetime.utcnow(),
        "end_time": None,
        "focus_intervals": [],
        "metrics": {
            "studying_time": 0,
            "distracted_time": 0,
            "away_time": 0,
            "total_alerts": 0,
            "focus_score": 0
        },
        "recent_alerts": [],
        **session_data
    }
    result = sessions_collection.insert_one(session)
    return result.inserted_id

def update_session(session_id, update_data: dict):
    """Update existing session"""
    sessions_collection.update_one(
        {"_id": session_id},
        {"$set": update_data}
    )

def get_current_session(user_id):
    """Get active session for user"""
    return sessions_collection.find_one({
        "user_id": user_id,
        "end_time": None
    })

def end_session(session_id, metrics: dict):
    """End session and update user stats"""
    session = sessions_collection.find_one({"_id": session_id})
    if not session:
        return
    
    update_data = {
        "end_time": datetime.utcnow(),
        "metrics": metrics
    }
    sessions_collection.update_one(
        {"_id": session_id},
        {"$set": update_data}
    )
    
    study_hours = metrics.get("studying_time", 0) / 3600
    
    # Update user's total stats
    users_collection.update_one(
        {"_id": session["user_id"]},
        {
            "$inc": {
                "total_sessions": 1,
                "total_focus_hours": study_hours
            }
        }
    )
    
    # Update global stats
    app_stats_collection.update_one(
        {"_id": "global_stats"},
        {
            "$inc": {
                "total_sessions": 1,
                "total_study_hours": study_hours
            },
            "$set": {"last_updated": datetime.utcnow()}
        }
    )

def get_user_lifetime_stats(user_id):
    """Calculate comprehensive user statistics"""
    all_sessions = list(sessions_collection.find({
        "user_id": user_id,
        "end_time": {"$ne": None}
    }))
    
    if not all_sessions:
        return {
            "total_sessions": 0,
            "total_study_hours": 0,
            "average_focus_score": 0,
            "total_alerts": 0,
            "longest_session": 0,
            "current_streak": 0,
            "best_focus_score": 0
        }
    
    # Calculate totals
    total_studying = sum(s.get("metrics", {}).get("studying_time", 0) for s in all_sessions)
    total_alerts = sum(s.get("metrics", {}).get("total_alerts", 0) for s in all_sessions)
    
    # Average focus score
    focus_scores = [s.get("metrics", {}).get("focus_score", 0) for s in all_sessions 
                   if s.get("metrics", {}).get("focus_score", 0) > 0]
    avg_focus_score = sum(focus_scores) / len(focus_scores) if focus_scores else 0
    best_focus_score = max(focus_scores) if focus_scores else 0
    
    # Longest session
    longest_session = max([s.get("metrics", {}).get("studying_time", 0) for s in all_sessions], default=0)
    
    # Calculate streak
    dates_with_sessions = set()
    for session in all_sessions:
        date_key = session["start_time"].strftime("%Y-%m-%d")
        dates_with_sessions.add(date_key)
    
    current_streak = 0
    date_check = datetime.utcnow().date()
    while date_check.isoformat() in dates_with_sessions:
        current_streak += 1
        date_check -= timedelta(days=1)
    
    return {
        "total_sessions": len(all_sessions),
        "total_study_hours": round(total_studying / 3600, 1),
        "average_focus_score": round(avg_focus_score, 1),
        "best_focus_score": round(best_focus_score, 1),
        "total_alerts": total_alerts,
        "longest_session": int(longest_session),
        "current_streak": current_streak
    }

def get_analytics_for_period(user_id, period: str):
    """Get analytics for day/week/month"""
    now = datetime.utcnow()
    
    if period == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    sessions = list(sessions_collection.find({
        "user_id": user_id,
        "start_time": {"$gte": start_date},
        "end_time": {"$ne": None}
    }))
    
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
                "distracted": 0,
                "sessions": 0
            }
        
        daily_breakdown[date_key]["studying"] += session.get("metrics", {}).get("studying_time", 0)
        daily_breakdown[date_key]["distracted"] += (
            session.get("metrics", {}).get("away_time", 0) + 
            session.get("metrics", {}).get("distracted_time", 0)
        )
        daily_breakdown[date_key]["sessions"] += 1
    
    return {
        "total_studying_hours": round(total_studying / 3600, 1),
        "total_sessions": len(sessions),
        "focus_score": round(focus_score, 1),
        "total_alerts": total_alerts,
        "daily_breakdown": daily_breakdown
    }

def get_all_users_summary():
    """Get summary of all users (admin function)"""
    total_users = users_collection.count_documents({})
    
    # Users registered today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    new_users_today = users_collection.count_documents({
        "created_at": {"$gte": today_start}
    })
    
    # Active users (logged in within last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    active_users = users_collection.count_documents({
        "last_login": {"$gte": week_ago}
    })
    
    return {
        "total_users": total_users,
        "new_users_today": new_users_today,
        "active_users_7_days": active_users
    }

# Print initial stats when module loads
try:
    stats = get_app_stats()
    print(f"\n📊 Focus Tracker Statistics:")
    print(f"   Total Users: {stats['total_users']}")
    print(f"   Total Sessions: {stats['total_sessions']}")
    print(f"   Total Study Hours: {stats['total_study_hours']}\n")
except Exception as e:
    print(f"⚠️  Could not load app statistics: {e}")