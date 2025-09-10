# Shared utility functions for unit tests

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))
from database import get_cursor, get_connection, MYSQL_DATABASE
from utils import generate_user_id, generate_api_key, hash_api_key
import setup

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

def clean_tables():
    """Clean up all test tables"""
    # Ensure database is set up
    setup.setup_database()
    cursor = get_cursor()
    cursor.execute(f"USE {MYSQL_DATABASE}")
    cursor.execute("DELETE FROM users")
    cursor.execute("DELETE FROM calendar_entries")
    cursor.execute("DELETE FROM tasks")
    cursor.execute("DELETE FROM notes")
    cursor.execute("DELETE FROM apps")
    cursor.execute("DELETE FROM app_user_links")
    get_connection().commit()
    # Create a new admin user to avoid issues with missing admin
    admin_id = generate_user_id()
    admin_key = generate_api_key()
    admin_hash = hash_api_key(admin_key)
    cursor.execute("INSERT INTO users (id, api_key_hash, role) VALUES (%s, %s, 'admin')", 
                   (admin_id, admin_hash))
    # Commit changes
    get_connection().commit()

def manual_admin_key_override():
    """Override the API key directly in the database for testing purposes"""
    apiKey = generate_api_key()
    apiHash = hash_api_key(apiKey)
    cursor = get_cursor()
    cursor.execute(f"USE {MYSQL_DATABASE}")
    # Check if an admin user already exists
    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    admin_user = cursor.fetchone()
    if admin_user:
        # Update existing admin user
        cursor.execute("UPDATE users SET api_key_hash = %s WHERE role = 'admin'", (apiHash,))
    else:
        # Create a new admin user
        admin_id = generate_user_id()
        cursor.execute("INSERT INTO users (id, api_key_hash, role) VALUES (%s, %s, 'admin')",
                       (admin_id, apiHash))
    get_connection().commit()
    return apiKey

def clear_all_tables():
    """
    Truncates all user-data tables to ensure test isolation.
    This should be called at the beginning of each test function that
    interacts with the database to prevent state from leaking between tests.
    """
    cursor = database.get_cursor()
    db_name = database.MYSQL_DATABASE
    cursor.execute(f"USE {db_name}")
    
    # Temporarily disable foreign key checks to allow truncating in any order
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    tables = ["app_user_links", "apps", "calendar_entries", "tasks", "notes", "users"]
    for table in tables:
        cursor.execute(f"TRUNCATE TABLE {table}")
        
    # Re-enable foreign key checks
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    database.get_connection().commit()