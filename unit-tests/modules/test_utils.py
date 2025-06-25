"""
Tests for app/utils.py helper functions.
"""

import pytest
from datetime import datetime
from fastapi import HTTPException
import sys
import os

# Add app and root directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import utils directly 
import utils
from utils import (
    generate_user_id,
    generate_api_key,
    hash_api_key,
    list_to_json,
    validate_time_format,
    handle_rrule_query,
    ResourceType,
    validate_api_key,
    validate_user_for_action,
    validate_entry_access
)
from unit_test_utils import (
    setup_test_database,
    cleanup_test_database,
    create_test_user,
    clean_test_data
)


class TestAppUtils:
    """Tests for the app/utils.py helper functions"""

    def test_generate_user_id(self):
        """Test that generate_user_id returns an 8-character alphanumeric string"""
        user_id = generate_user_id()
        assert isinstance(user_id, str)
        assert len(user_id) == 8
        assert user_id.isalnum()

    def test_generate_api_key(self):
        """Test that generate_api_key returns a non-empty string"""
        api_key = generate_api_key()
        assert isinstance(api_key, str)
        assert len(api_key) > 0

    def test_hash_api_key(self):
        """Test that hash_api_key returns a consistent SHA-256 hash"""
        api_key = "my-secret-key"
        hashed_key = hash_api_key(api_key)
        # Test that it's a valid hex string of the right length for SHA-256
        assert len(hashed_key) == 64
        assert all(c in '0123456789abcdef' for c in hashed_key)
        # Test consistency - same input should always produce same output
        assert hashed_key == hash_api_key(api_key)

    def test_list_to_json(self):
        """Test that list_to_json converts a list to a JSON string"""
        my_list = ["a", "b", 1, 2]
        json_str = list_to_json(my_list)
        assert json_str == '["a", "b", 1, 2]'

    def test_list_to_json_empty_or_none(self):
        """Test that list_to_json handles empty and None lists correctly"""
        assert list_to_json([]) is None
        assert list_to_json(None) is None

    def test_validate_time_format(self):
        """Test that validate_time_format correctly parses ISO 8601 strings"""
        valid_time_str = "2024-01-01T12:00:00"
        dt_obj = validate_time_format(valid_time_str)
        assert isinstance(dt_obj, datetime)
        assert dt_obj.year == 2024
        assert dt_obj.month == 1
        assert dt_obj.day == 1

    def test_validate_time_format_invalid(self):
        """Test that validate_time_format returns None for invalid strings"""
        invalid_time_str = "not-a-valid-date"
        assert validate_time_format(invalid_time_str) is None

    def test_handle_rrule_query_with_events(self):
        """Test that handle_rrule_query raises a 501 Not Implemented error"""
        with pytest.raises(HTTPException) as exc_info:
            handle_rrule_query([{"id": 1}], "2024-01-01", "2024-01-31")
        assert exc_info.value.status_code == 501
        assert "not yet supported" in exc_info.value.detail

    def test_handle_rrule_query_no_events(self):
        """Test that handle_rrule_query returns an empty list when no events are passed"""
        assert handle_rrule_query([], "2024-01-01", "2024-01-31") == []

    def test_resource_type_enum(self):
        """Test the ResourceType enum"""
        assert ResourceType.CALENDAR == "calendar"
        assert ResourceType.TASK == "task"
        assert ResourceType.NOTE == "note"


@pytest.mark.usefixtures("db_connection")
class TestDatabaseUtils:
    """Tests for database-dependent utility functions in app/utils.py"""

    @pytest.fixture(scope="class")
    def db_connection(self):
        """Setup and teardown database connection for tests"""
        conn, cursor = setup_test_database()
        yield conn, cursor
        cleanup_test_database()

    @pytest.fixture(autouse=True)
    def clean_db(self, db_connection):
        """Clean database before each test in this class"""
        _, cursor = db_connection
        clean_test_data(cursor)

    def test_validate_api_key(self, db_connection):
        """Test API key validation logic"""
        conn, cursor = db_connection
        create_test_user(cursor, user_id="tuser1", role="user", api_key="user_key")
        create_test_user(cursor, user_id="tadmin1", role="admin", api_key="admin_key")
        conn.commit()

        # Valid user key
        user_id, role, perm = validate_api_key("user_key", "tuser1")
        assert user_id == "tuser1"
        assert role == "user"
        assert perm is True

        # Admin key has permission on user
        user_id, role, perm = validate_api_key("admin_key", "tuser1")
        assert user_id == "tadmin1"
        assert role == "admin"
        assert perm is True

        # User key does not have permission on admin
        user_id, role, perm = validate_api_key("user_key", "tadmin1")
        assert user_id == "tuser1"
        assert role == "user"
        assert perm is False

        # Invalid key
        user_id, role, perm = validate_api_key("invalid_key")
        assert user_id is None
        assert role is None
        assert perm is False

    def test_validate_user_for_action(self, db_connection):
        """Test user action validation logic"""
        conn, cursor = db_connection
        create_test_user(cursor, user_id="tuser2", role="user", api_key="user_key_act")
        create_test_user(cursor, user_id="tadmin2", role="admin", api_key="admin_key_act")
        conn.commit()

        # User acting on self
        assert validate_user_for_action("user_key_act", "tuser2") == "tuser2"
        assert validate_user_for_action("user_key_act") == "tuser2"

        # User trying to act on another
        with pytest.raises(HTTPException) as exc:
            validate_user_for_action("user_key_act", "tadmin2")
        assert exc.value.status_code == 403

        # Admin acting on user
        assert validate_user_for_action("admin_key_act", "tuser2") == "tuser2"

        # Admin acting on self
        with pytest.raises(HTTPException) as exc:
            validate_user_for_action("admin_key_act", "tadmin2")
        assert exc.value.status_code == 400

        # Admin must specify user
        with pytest.raises(HTTPException) as exc:
            validate_user_for_action("admin_key_act")
        assert exc.value.status_code == 400

        # Invalid API key
        with pytest.raises(HTTPException) as exc:
            validate_user_for_action("invalid_key", "tuser2")
        assert exc.value.status_code == 403

    def test_validate_entry_access(self, db_connection):
        """Test resource entry access validation logic"""
        conn, cursor = db_connection

        # Create test users
        create_test_user(cursor, user_id="tuser3", role="user", api_key="user_key_res")
        create_test_user(cursor, user_id="tuser4", role="user", api_key="user_key_res2")
        create_test_user(cursor, user_id="tadmin3", role="admin", api_key="admin_key_res")

        # Create test resource entries
        cursor.execute(f"USE {utils.database.MYSQL_DATABASE}")

        # Create a calendar entry for tuser3
        cursor.execute(
            "INSERT INTO calendar_entries (id, user_id, title, start_datetime, end_datetime) VALUES (%s, %s, %s, %s, %s)",
            (1, "tuser3", "Test Event", "2024-01-01T09:00:00", "2024-01-01T10:00:00")
        )

        # Create a task for tuser4
        cursor.execute(
            "INSERT INTO tasks (id, user_id, title, due_date) VALUES (%s, %s, %s, %s)",
            (1, "tuser4", "Test Task", "2024-01-02")
        )

        # Create a note for tuser3
        cursor.execute(
            "INSERT INTO notes (id, user_id, title, content) VALUES (%s, %s, %s, %s)",
            (1, "tuser3", "Test Note", "This is a test note")
        )

        conn.commit()

        # Test 1: User can access their own calendar entry
        user_id, role = validate_entry_access("user_key_res", ResourceType.CALENDAR, 1)
        assert user_id == "tuser3"
        assert role == "user"

        # Test 2: User cannot access another user's task
        with pytest.raises(HTTPException) as exc:
            validate_entry_access("user_key_res", ResourceType.TASK, 1)
        assert exc.value.status_code == 403
        assert "Access denied" in exc.value.detail

        # Test 3: Admin can access any user's entry
        user_id, role = validate_entry_access("admin_key_res", ResourceType.NOTE, 1)
        assert user_id == "tadmin3"
        assert role == "admin"

        # Test 4: Invalid resource type
        with pytest.raises(HTTPException) as exc:
            validate_entry_access("user_key_res", "invalid_type", 1)
        assert exc.value.status_code == 500
        assert "Invalid resource type" in exc.value.detail

        # Test 5: Resource entry not found
        with pytest.raises(HTTPException) as exc:
            validate_entry_access("user_key_res", ResourceType.CALENDAR, 999)
        assert exc.value.status_code == 404
        assert "entry not found" in exc.value.detail

        # Test 6: Invalid API key
        with pytest.raises(HTTPException) as exc:
            validate_entry_access("invalid_key", ResourceType.CALENDAR, 1)
        assert exc.value.status_code == 403
        assert "Invalid API key" in exc.value.detail

    def test_validate_api_key_exception_handling(self, db_connection):
        """Test that validate_api_key handles database exceptions gracefully"""
        # Force an exception by closing the database connection
        conn, _ = db_connection
        conn.close()

        # This should return None, None, False due to exception handling
        user_id, role, perm = validate_api_key("any_key")
        assert user_id is None
        assert role is None
        assert perm is False
