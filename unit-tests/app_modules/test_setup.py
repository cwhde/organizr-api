# Test the API's setup module

import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
import setup
import database

def test_check_db_is_setup():
    # Close any existing connections to ensure clean state
    database.close_connection()
    
    cursor = database.get_cursor()
    cursor.execute(f"DROP DATABASE IF EXISTS {database.MYSQL_DATABASE}")
    database.get_connection().commit()
    
    # Test with no database
    assert not setup.check_db_is_setup()
    
    # Test with database but no tables
    cursor = database.get_cursor()
    cursor.execute(f"CREATE DATABASE {database.MYSQL_DATABASE}")
    database.get_connection().commit()
    assert not setup.check_db_is_setup()
    
    # Test with complete setup
    setup.create_db_and_scheme()
    assert setup.check_db_is_setup()

def test_create_db_and_scheme():
    # Close any existing connections to ensure clean state
    database.close_connection()
    
    cursor = database.get_cursor()
    cursor.execute(f"DROP DATABASE IF EXISTS {database.MYSQL_DATABASE}")
    database.get_connection().commit()
    
    setup.create_db_and_scheme()
    
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("SHOW TABLES")
    tables = [table[0] for table in cursor.fetchall()]
    required_tables = ["users", "calendar_entries", "tasks", "notes", "apps", "app_user_links"]
    assert all(table in tables for table in required_tables)

def test_create_admin_user():
    setup.create_db_and_scheme()
    
    admin_id, _ = setup.create_admin_user()
    
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND id = %s", (admin_id,))
    assert cursor.fetchone()[0] == 1

def test_setup_database():
    # Close any existing connections to ensure clean state
    database.close_connection()
    
    cursor = database.get_cursor()
    cursor.execute(f"DROP DATABASE IF EXISTS {database.MYSQL_DATABASE}")
    database.get_connection().commit()
    
    # First time should setup and return True
    result = setup.setup_database()
    assert result == True
    
    # Second time should skip and return False
    result = setup.setup_database()
    assert result == False