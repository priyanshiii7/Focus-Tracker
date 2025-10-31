from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import base64
from bson import ObjectId

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["focus_tracker"]

# Collections
users_collection = db["users"]
sessions_collection = db["sessions"]

def get_or_create_user(name: str, email: str = None):
    """Get existing user or create new one"""
    user = users_collection.find_one({"name": name})
    
    if not user:
        user = {
            "name": name,
            "email": email,
            "created_at": datetime.utcnow(),
            "total_sessions": 0,
            "total_focus_hours": 0.0,
            "background_theme": "gradient-purple",
            "profile_picture_data": None,  # Store base64 image data
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
    
    # Update user's total stats
    users_collection.update_one(
        {"_id": session["user_id"]},
        {
            "$inc": {
                "total_sessions": 1,
                "total_focus_hours": metrics.get("studying_time", 0) / 3600
            }
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
            "current_streak": 0
        }
    
    # Calculate totals
    total_studying = sum(s.get("metrics", {}).get("studying_time", 0) for s in all_sessions)
    total_alerts = sum(s.get("metrics", {}).get("total_alerts", 0) for s in all_sessions)
    
    # Average focus score
    focus_scores = [s.get("metrics", {}).get("focus_score", 0) for s in all_sessions 
                   if s.get("metrics", {}).get("focus_score", 0) > 0]
    avg_focus_score = sum(focus_scores) / len(focus_scores) if focus_scores else 0
    
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

def save_profile_picture(user_name: str, image_data: bytes):
    """Save profile picture as base64 in database"""
    base64_image = base64.b64encode(image_data).decode('utf-8')
    
    users_collection.update_one(
        {"name": user_name},
        {"$set": {"profile_picture_data": base64_image}}
    )
    
    return base64_image

def get_profile_picture(user_name: str):
    """Get profile picture from database"""
    user = users_collection.find_one({"name": user_name})
    if user and user.get("profile_picture_data"):
        return user["profile_picture_data"]
    return None