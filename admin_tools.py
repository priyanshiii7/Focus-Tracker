#!/usr/bin/env python3
"""
Admin tools for Focus Tracker
Usage:
    python admin_tools.py maintenance on
    python admin_tools.py maintenance off
    python admin_tools.py status
"""

import requests
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

def enable_maintenance():
    """Enable maintenance mode"""
    try:
        response = requests.post(
            f"{API_URL}/api/admin/maintenance",
            json={"enable": True, "admin_key": ADMIN_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Maintenance mode ENABLED")
            print("🔒 Users will see maintenance page")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.json())
    except Exception as e:
        print(f"❌ Failed to enable maintenance: {e}")

def disable_maintenance():
    """Disable maintenance mode"""
    try:
        response = requests.post(
            f"{API_URL}/api/admin/maintenance",
            json={"enable": False, "admin_key": ADMIN_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Maintenance mode DISABLED")
            print("🎉 App is now accessible to users")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.json())
    except Exception as e:
        print(f"❌ Failed to disable maintenance: {e}")

def check_status():
    """Check current status"""
    try:
        # Check maintenance status
        maintenance = requests.get(f"{API_URL}/api/maintenance", timeout=10)
        
        # Check version
        version = requests.get(f"{API_URL}/version", timeout=10)
        
        # Check stats
        stats = requests.get(f"{API_URL}/api/stats", timeout=10)
        
        print("=" * 60)
        print("📊 FOCUS TRACKER STATUS")
        print("=" * 60)
        
        if maintenance.status_code == 200:
            m_data = maintenance.json()
            status = "🔒 MAINTENANCE MODE" if m_data.get("maintenance_mode") else "✅ OPERATIONAL"
            print(f"Status: {status}")
        
        if version.status_code == 200:
            v_data = version.json()
            print(f"Version: {v_data.get('version', 'Unknown')}")
            print(f"Updated: {v_data.get('updated', 'Unknown')}")
        
        if stats.status_code == 200:
            s_data = stats.json()
            if s_data.get("success"):
                st = s_data["stats"]
                print(f"\nTotal Users: {st.get('total_users', 0)}")
                print(f"Total Sessions: {st.get('total_sessions', 0)}")
                print(f"Study Hours: {st.get('total_study_hours', 0)}")
                print(f"Active (7d): {st.get('active_users_7_days', 0)}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Failed to check status: {e}")

def generate_admin_key():
    """Generate a new admin key"""
    import secrets
    key = secrets.token_urlsafe(32)
    print("🔑 New Admin Key Generated:")
    print("-" * 60)
    print(key)
    print("-" * 60)
    print("\n⚠️  IMPORTANT:")
    print("1. Add this to your .env file:")
    print(f"   ADMIN_KEY={key}")
    print("2. Never commit this key to Git!")
    print("3. Update it on your deployment platform")

def show_help():
    """Show help message"""
    print("""
🛠️  Focus Tracker Admin Tools

Usage:
    python admin_tools.py <command>

Commands:
    maintenance on     Enable maintenance mode
    maintenance off    Disable maintenance mode
    status            Check app status
    generate-key      Generate new admin key
    help              Show this help message

Examples:
    python admin_tools.py maintenance on
    python admin_tools.py status
    python admin_tools.py generate-key

Configuration:
    Set these in .env file:
    - API_URL (default: http://localhost:8000)
    - ADMIN_KEY (required for maintenance commands)
    """)

def main():
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "maintenance":
        if len(sys.argv) < 3:
            print("❌ Usage: python admin_tools.py maintenance [on|off]")
            sys.exit(1)
        
        if not ADMIN_KEY:
            print("❌ ADMIN_KEY not set in .env file!")
            print("💡 Run: python admin_tools.py generate-key")
            sys.exit(1)
        
        action = sys.argv[2].lower()
        if action == "on":
            enable_maintenance()
        elif action == "off":
            disable_maintenance()
        else:
            print("❌ Invalid action. Use 'on' or 'off'")
    
    elif command == "status":
        check_status()
    
    elif command == "generate-key":
        generate_admin_key()
    
    elif command == "help":
        show_help()
    
    else:
        print(f"❌ Unknown command: {command}")
        show_help()
        sys.exit(1)

if __name__ == "__main__":
    main()