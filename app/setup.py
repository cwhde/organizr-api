# Setup module for the Organizr API
import logging
import utils
import database

logger = logging.getLogger(__name__)


def check_db_is_setup():
    """Check if the organizr database exists and contains all required tables."""
    db_cursor = database.get_cursor()
    db_cursor.execute("SHOW DATABASES")
    databases = [db[0] for db in db_cursor.fetchall()]
    
    if database.MYSQL_DATABASE not in databases:
        return False
    
    db_cursor.execute(f"USE {database.MYSQL_DATABASE}")
    db_cursor.execute("SHOW TABLES")
    tables = [table[0] for table in db_cursor.fetchall()]

    database.get_connection().commit()
    
    required_tables = ["users", "calendar_entries", "tasks", "notes", "apps", "app_user_links"]

    return all(table in tables for table in required_tables)


def create_db_and_scheme():
    """Create the organizr database and all necessary tables."""
    db_cursor = database.get_cursor()

    # Create database and select it
    db_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database.MYSQL_DATABASE};")
    db_cursor.execute(f"USE {database.MYSQL_DATABASE};")
    # Create tables
    db_cursor.execute(
        """
        -- User table
        CREATE TABLE IF NOT EXISTS users (
            id                   CHAR(8)      PRIMARY KEY,
            api_key_hash         CHAR(64)     NOT NULL,
            utc_offset_minutes   SMALLINT     NULL,
            role                 ENUM('user','admin') NOT NULL DEFAULT 'user',
            created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
        -- Calendar entries
        CREATE TABLE IF NOT EXISTS calendar_entries (
            id                   INT          AUTO_INCREMENT PRIMARY KEY,
            user_id              CHAR(8)      NOT NULL,
            title                VARCHAR(255) NOT NULL,
            description          TEXT         NULL,
            start_datetime       DATETIME     NOT NULL,
            end_datetime         DATETIME     NOT NULL,
            rrule                TEXT         NULL,
            tags                 JSON         NULL,
            created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        -- Tasks
        CREATE TABLE IF NOT EXISTS tasks (
            id                   INT          AUTO_INCREMENT PRIMARY KEY,
            user_id              CHAR(8)      NOT NULL,
            title                VARCHAR(255) NOT NULL,
            description          TEXT         NULL,
            status               ENUM('pending','in_progress','completed','cancelled') NOT NULL DEFAULT 'pending',
            due_date             DATETIME     NULL,
            rrule                TEXT         NULL,
            tags                 JSON         NULL,
            created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        -- Notes
        CREATE TABLE IF NOT EXISTS notes (
            id                   INT          AUTO_INCREMENT PRIMARY KEY,
            user_id              CHAR(8)      NOT NULL,
            title                VARCHAR(255) NOT NULL,
            content              TEXT         NOT NULL,
            tags                 JSON         NULL,
            created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        -- Apps
        CREATE TABLE IF NOT EXISTS apps (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        -- App User Links
        CREATE TABLE IF NOT EXISTS app_user_links (
            id INT AUTO_INCREMENT PRIMARY KEY,
            app_id INT,
            user_id CHAR(8),
            external_id VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (app_id, external_id),
            UNIQUE (app_id, user_id)
        );
        """
    )

    database.get_connection().commit()


def create_admin_user():
    """Create the initial admin user and log credentials."""
    db_cursor = database.get_cursor()

    # Generate admin credentials
    admin_id = utils.generate_user_id()
    admin_api_key = utils.generate_api_key()
    api_key_hash = utils.hash_api_key(admin_api_key)

    # Insert admin user into database
    db_cursor.execute(f"USE {database.MYSQL_DATABASE}")
    db_cursor.execute(
        "INSERT INTO users (id, api_key_hash, role) VALUES (%s, %s, 'admin')",
        (admin_id, api_key_hash)
    )

    database.get_connection().commit()

    # Log credentials (will appear in Docker logs)
    logger.info("=" * 60)
    logger.info("ORGANIZR-API ADMIN USER CREATED")
    logger.info(f"Admin User ID: {admin_id}")
    logger.info(f"Admin API Key: {admin_api_key}")
    logger.info("SAVE THESE CREDENTIALS - THEY WILL NOT BE SHOWN AGAIN!")
    logger.info("Use these credentials to manage users via the API.")
    logger.info("=" * 60)

    return admin_id, admin_api_key


def setup_database():
    """Ensure the database is configured, create schema and admin user if needed."""
    logger.info("Checking if the database is set up...")
    if not check_db_is_setup():
        logger.info("Database not found or incomplete. Setting up...")
        create_db_and_scheme()
        logger.info("Database and tables created successfully.")
        create_admin_user()
        logger.info("Admin user created successfully.")

        database.get_connection().commit()

        return True
    else:
        logger.info("Database is already set up.")

        database.get_connection().commit()

        return False