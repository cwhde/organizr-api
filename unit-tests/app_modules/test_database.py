# Test the database module

import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
import database
import mysql.connector
from unittest.mock import patch
import unit_test_utils

@pytest.fixture(scope="module", autouse=True)
def setup_module():
    """Setup the database for the module."""
    unit_test_utils.clean_tables()

def test_get_connection():
    conn = database.get_connection()
    assert conn.is_connected()

def test_get_cursor():
    cursor = database.get_cursor()
    assert cursor is not None
    cursor.close()

def test_database_operations():
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("CREATE TEMPORARY TABLE test_table (id INT, name VARCHAR(50))")
    cursor.execute("INSERT INTO test_table VALUES (1, 'test')")
    cursor.execute("SELECT * FROM test_table WHERE id = 1")
    result = cursor.fetchone()
    assert result == (1, 'test')
    cursor.close()

def test_connection_with_bad_creds():
    original_password = database.MYSQL_PASSWORD
    database.MYSQL_PASSWORD = "wrong_password"
    database._connection = None
    with pytest.raises(mysql.connector.Error):
        database.get_connection()
    database.MYSQL_PASSWORD = original_password
    database._connection = None

def test_close_connection():
    database.get_connection()
    assert database._connection.is_connected()
    database.close_connection()
    assert database._connection is None