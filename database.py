from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["focus_tracker"]

# Collections
users_collection = db["users"]
sessions_collection = db["sessions"]
daily_stats_collection = db["daily_stats"]

def get_or_create_user(name: str, email: str = None):
    """Get existing user or create new one"""
    user = users_collection.find_one({"name": name})
    
    if not user:
        user = {
            "name": name,
            "email": email,
            "created_at": datetime.utcnow(),
            "total_sessions": 0,
            "total_focus_hours": 0.0
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
            "focus_time": 0,
            "break_time": 0,
            "away_time": 0,
            "phone_detections": 0,
            "focus_score": 0
        },
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

def get_today_sessions(user_id):
    """Get all sessions from today"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return list(sessions_collection.find({
        "user_id": user_id,
        "start_time": {"$gte": today_start}
    }))

def end_session(session_id, metrics: dict):
    """End session and update stats"""
    update_data = {
        "end_time": datetime.utcnow(),
        "metrics": metrics
    }
    sessions_collection.update_one(
        {"_id": session_id},
        {"$set": update_data}
    )