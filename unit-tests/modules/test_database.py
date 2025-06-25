"""
Tests for app/database.py module.
"""

import unittest
from unittest.mock import patch, MagicMock
import mysql.connector
import sys
import os

# Add app and root directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database
from unit_test_utils import setup_test_database, cleanup_test_database

class TestDatabase(unittest.TestCase):
    """Tests for the app/database.py module"""

    def setUp(self):
        """Set up test database"""
        self.conn, self.cursor = setup_test_database()

    def tearDown(self):
        """Clean up test database"""
        cleanup_test_database()

    def test_get_connection(self):
        """Test that get_connection returns a valid connection"""
        conn = database.get_connection()
        self.assertIsNotNone(conn)
        self.assertTrue(conn.is_connected())

    def test_get_cursor(self):
        """Test that get_cursor returns a valid cursor"""
        cursor = database.get_cursor()
        self.assertIsNotNone(cursor)

    def test_close_connection(self):
        """Test that close_connection closes the connection"""
        database.close_connection()
        self.assertIsNone(database._connection)

    def test_connection_is_reused(self):
        """Test that the same connection object is reused"""
        conn1 = database.get_connection()
        conn2 = database.get_connection()
        self.assertIs(conn1, conn2)

    @patch('mysql.connector.connect')
    def test_get_connection_failure(self, mock_connect):
        """Test that get_connection raises an exception on connection failure"""
        # Ensure the global connection is reset for this test
        database._connection = None

        mock_connect.side_effect = mysql.connector.Error("Connection failed")

        with self.assertRaises(mysql.connector.Error):
            database.get_connection()

if __name__ == '__main__':
    unittest.main()
