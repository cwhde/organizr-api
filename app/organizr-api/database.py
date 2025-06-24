# Database connection management module
import os
from typing import Optional
import mysql.connector
import logging

logger = logging.getLogger(__name__)

_connection: Optional[mysql.connector.connection.MySQLConnection] = None

# Environment variables for database connection
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "organizr")

def get_connection():
    """Get database connection, create if not exists"""
    global _connection
    
    if _connection is None or not _connection.is_connected():
        try:
            _connection = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                port=MYSQL_PORT,
                database=MYSQL_DATABASE,
                autocommit=False
            )
            logger.info("Database connection established")
        except mysql.connector.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    return _connection

def get_cursor():
    """Get a new cursor from the database connection"""
    conn = get_connection()
    return conn.cursor()

def close_connection():
    """Close database connection"""
    global _connection
    if _connection and _connection.is_connected():
        _connection.close()
        _connection = None
        logger.info("Database connection closed")