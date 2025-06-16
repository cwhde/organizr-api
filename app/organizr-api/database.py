# Database connection management module
import os
import mysql.connector
import logging

logger = logging.getLogger(__name__)

_connection = None

def get_connection():
    """Get database connection, create if not exists"""
    global _connection
    
    if _connection is None or not _connection.is_connected():
        try:
            _connection = mysql.connector.connect(
                host=os.getenv("MYSQL_HOST", "localhost"),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                port=int(os.getenv("MYSQL_PORT", "3306")),
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