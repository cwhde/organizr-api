"""
Shared test utilities, fixtures, and helper functions
Simple and explicit test helpers - no magic pytest fixtures
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import database


def setup_test_database():
    """
    Set up the test database connection
    Call this at the start of tests that need database access
    """
    print(f"Setting up test database: {database.MYSQL_DATABASE}")
    
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    
    return conn, cursor


def cleanup_test_database():
    """
    Clean up database connection
    Call this at the end of tests
    """
    print("Cleaning up test database")
    database.close_connection()


def create_test_user(cursor, user_id="test_user_123", role="user", api_key="test_api_key_123"):
    """
    Create a test user in the database
    Returns the user data that was inserted
    """
    from utils import hash_api_key
    
    api_key_hash = hash_api_key(api_key)
    
    # Insert test user
    cursor.execute(
        "INSERT INTO users (id, role, api_key_hash) VALUES (%s, %s, %s)",
        (user_id, role, api_key_hash)
    )
    
    return {
        "id": user_id,
        "role": role,
        "api_key": api_key,
        "api_key_hash": api_key_hash
    }


def clean_test_data(cursor):
    """
    Remove any test data from the database
    Call this before/after tests to ensure clean state
    """
    cursor.execute("DELETE FROM users WHERE id LIKE 't%'")
    cursor.execute("DELETE FROM calendar_entries WHERE user_id LIKE 't%'")
    cursor.execute("DELETE FROM tasks WHERE user_id LIKE 't%'")
    cursor.execute("DELETE FROM notes WHERE user_id LIKE 't%'")


def sample_user_data():
    """
    Return sample user data for testing
    """
    return {
        "id": "test_user_123",
        "role": "user",
        "api_key": "test_api_key_123",
        "api_key_hash": "hashed_test_key"
    }


def sample_admin_data():
    """
    Return sample admin user data for testing
    """
    return {
        "id": "test_admin_456",
        "role": "admin",
        "api_key": "test_admin_key_456",
        "api_key_hash": "hashed_admin_key"
    }
