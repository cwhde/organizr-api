"""
Tests for app/schemas.py module
Tests Pydantic models for validation, serialization, and data integrity
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

# Import the schemas we want to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))

from schemas import (
    User, UserWithOffset, CalendarEvent, CalendarEventCreate, 
    MessageResponse, App, TranslateIdResponse
)


# Reusable data
NOW = datetime.now()
USER_DATA = {"id": "user123", "role": "admin", "created_at": NOW, "updated_at": NOW}
START_TIME = datetime(2024, 1, 1, 10, 0)
END_TIME = datetime(2024, 1, 1, 11, 0)
EVENT_DATA = {
    "id": 1, "user_id": "user123", "title": "Test Meeting",
    "start_datetime": START_TIME, "end_datetime": END_TIME
}


class TestSchemas:
    """Consolidated tests for Pydantic models in schemas.py"""

    def test_user_creation(self):
        """Test User model creation with and without optional fields."""
        user = User(**USER_DATA)
        assert user.id == "user123"
        assert user.role == "admin"

        minimal_user = User(id="user456", role="user")
        assert minimal_user.created_at is None
        assert minimal_user.updated_at is None

    @pytest.mark.parametrize("invalid_data", [
        {},
        {"id": 123, "role": "user"},
        {"id": "user123", "role": 123},
        {"id": "user123", "role": "user", "created_at": "not-a-datetime"}
    ])
    def test_user_validation_error(self, invalid_data):
        """Test User model validation for missing fields and invalid types."""
        with pytest.raises(ValidationError):
            User(**invalid_data)

    def test_user_with_offset_creation(self):
        """Test UserWithOffset model creation."""
        user_with_offset = UserWithOffset(**USER_DATA, utc_offset_minutes=120)
        assert user_with_offset.utc_offset_minutes == 120

        user_without_offset = UserWithOffset(**USER_DATA)
        assert user_without_offset.utc_offset_minutes is None

    def test_calendar_event_creation(self):
        """Test CalendarEvent model creation with and without optional fields."""
        full_event = CalendarEvent(
            **EVENT_DATA,
            description="Important meeting",
            rrule="FREQ=WEEKLY",
            tags=["work", "important"]
        )
        assert full_event.description == "Important meeting"
        assert full_event.rrule == "FREQ=WEEKLY"
        assert full_event.tags == ["work", "important"]

        minimal_event = CalendarEvent(**EVENT_DATA)
        assert minimal_event.description is None
        assert minimal_event.rrule is None
        assert minimal_event.tags == []

    @pytest.mark.parametrize("invalid_data", [
        {},
        {"id": "not-an-int", "user_id": "user123", "title": "Test", "start_datetime": START_TIME, "end_datetime": END_TIME},
        {"id": 1, "user_id": "user123", "title": "Test", "start_datetime": "not-a-datetime", "end_datetime": END_TIME}
    ])
    def test_calendar_event_validation_error(self, invalid_data):
        """Test CalendarEvent model validation for missing fields and invalid types."""
        with pytest.raises(ValidationError):
            CalendarEvent(**invalid_data)

    def test_calendar_event_create(self):
        """Test CalendarEventCreate model creation."""
        create_data = {
            "id": 1, "user_id": "user123", "title": "Test Meeting",
            "start_datetime": "2024-01-01T10:00:00"
        }
        event = CalendarEventCreate(**create_data, end_datetime="2024-01-01T11:00:00")
        assert event.end_datetime == "2024-01-01T11:00:00"

        event_no_end = CalendarEventCreate(**create_data)
        assert event_no_end.end_datetime is None

    def test_message_response(self):
        """Test MessageResponse model."""
        response = MessageResponse(message="Success")
        assert response.message == "Success"
        with pytest.raises(ValidationError):
            MessageResponse()
        with pytest.raises(ValidationError):
            MessageResponse(message=123)

    def test_app_model(self):
        """Test App model."""
        app = App(id=1, name="Test App", created_at=NOW)
        assert app.name == "Test App"
        with pytest.raises(ValidationError):
            App(id="not-an-int", name="Test", created_at=NOW)

    def test_translate_id_response(self):
        """Test TranslateIdResponse model."""
        response = TranslateIdResponse(user_id="user123", external_id="ext456")
        assert response.user_id == "user123"
        assert response.external_id == "ext456"

        empty_response = TranslateIdResponse()
        assert empty_response.user_id is None
        assert empty_response.external_id is None
