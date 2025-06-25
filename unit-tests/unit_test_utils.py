import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))
from database import get_cursor, get_connection, MYSQL_DATABASE
from utils import generate_user_id, generate_api_key, hash_api_key

def setup_test_user():
    """Create test users properly like the app does"""
    cursor = get_cursor()
    cursor.execute(f"USE {MYSQL_DATABASE}")
    
    user_id = generate_user_id()
    api_key = generate_api_key()
    api_hash = hash_api_key(api_key)
    cursor.execute("INSERT INTO users (id, api_key_hash, role) VALUES (%s, %s, 'user')", 
                   (user_id, api_hash))
    
    admin_id = generate_user_id()
    admin_key = generate_api_key()
    admin_hash = hash_api_key(admin_key)
    cursor.execute("INSERT INTO users (id, api_key_hash, role) VALUES (%s, %s, 'admin')", 
                   (admin_id, admin_hash))
    
    get_connection().commit()
    return user_id, api_key, admin_id, admin_key

def cleanup_test_users():
    """Clean up test users"""
    cursor = get_cursor()
    cursor.execute(f"USE {MYSQL_DATABASE}")
    cursor.execute("DELETE FROM calendar_entries WHERE user_id IN (SELECT id FROM users WHERE LENGTH(id) = 8)")
    cursor.execute("DELETE FROM users WHERE LENGTH(id) = 8")
    get_connection().commit()

def create_test_calendar_entry(user_id):
    """Create test calendar entry"""
    cursor = get_cursor()
    cursor.execute(f"USE {MYSQL_DATABASE}")
    cursor.execute("INSERT INTO calendar_entries (user_id, title, start_datetime, end_datetime) VALUES (%s, %s, %s, %s)",
                   (user_id, "Test Event", "2023-01-01 10:00:00", "2023-01-01 11:00:00"))
    get_connection().commit()
    return cursor.lastrowid