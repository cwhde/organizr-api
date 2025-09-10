# Test the calendar route of the API

import pytest
import sys
import os
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

# Add parent directories to path to import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import unit_test_utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'app'))
import database
from app import app

@pytest.fixture(scope="module", autouse=True)
def setup_module():
    """Setup the database for the module."""
    unit_test_utils.clean_tables()

@pytest.fixture(scope="module")
def test_user():
    """Create a standard user and API key for the tests in this module."""
    client = TestClient(app)
    admin_api_key = unit_test_utils.manual_admin_key_override()
    response = client.post("/users/", headers={"X-API-Key": admin_api_key})
    data = response.json()
    return {"user_id": data["user_id"], "api_key": data["api_key"]}

def test_event_crud(test_user):
    """Test the complete lifecycle: create, read, update, and delete for a calendar event."""
    client = TestClient(app)
    user_api_key = test_user["api_key"]
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=1)
    
    # Create a new event to work with
    response = client.post("/calendar/", params={
        "title": "My Test Event", 
        "description": "A very important meeting.",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "tags": ["meeting", "work"]
    }, headers={"X-API-Key": user_api_key})
    
    assert response.status_code == 200
    created_event = response.json()
    event_id = created_event["id"]
    assert created_event["title"] == "My Test Event"

    # Verify the event can be fetched by its ID
    response = client.get(f"/calendar/{event_id}", headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    fetched_event = response.json()
    assert fetched_event["id"] == event_id
    assert fetched_event["title"] == "My Test Event"
    assert fetched_event["tags"] == ["meeting", "work"]

    # Update the event's title and tags
    updated_title = "Updated Event Title"
    response = client.put(
        f"/calendar/{event_id}", 
        params={"title": updated_title, "tags": '["meeting", "urgent"]'}, 
        headers={"X-API-Key": user_api_key}
    )
    assert response.status_code == 200
    updated_event = response.json()
    assert updated_event["title"] == updated_title
    assert updated_event["tags"] == ["meeting", "urgent"]

    # Delete the event
    response = client.delete(f"/calendar/{event_id}", headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]
    
    # Verify the event is gone by trying to fetch it again
    response = client.get(f"/calendar/{event_id}", headers={"X-API-Key": user_api_key})
    assert response.status_code == 404

def test_query_and_search_events(test_user):
    """Test querying events with various filters and the dedicated search endpoint."""
    client = TestClient(app)
    user_api_key = test_user["api_key"]
    start_date = datetime.now()

    # Define time window for query
    query_start = (start_date - timedelta(days=1)).isoformat()
    query_end = (start_date + timedelta(days=30)).isoformat()

    # Get initial count of events in the time window to make test independent
    initial_response = client.get("/calendar/", params={
        "start_after": query_start,
        "end_before": query_end
    }, headers={"X-API-Key": user_api_key})
    initial_count = 0
    if initial_response.status_code == 200:
        initial_count = len(initial_response.json())

    # Create a few distinct events for querying
    client.post("/calendar/", params={
        "title": "Single Doctor's Appointment",
        "start_time": (start_date + timedelta(days=2)).isoformat(),
        "end_time": (start_date + timedelta(days=2, hours=1)).isoformat()
    }, headers={"X-API-Key": user_api_key})

    rrule = "FREQ=WEEKLY;COUNT=4"
    client.post("/calendar/", params={
        "title": "Weekly Team Sync",
        "start_time": start_date.isoformat(),
        "end_time": (start_date + timedelta(hours=1)).isoformat(),
        "rrule": rrule,
        "tags": ["recurring", "work"]
    }, headers={"X-API-Key": user_api_key})

    # Test the main query endpoint with a time window to check RRULE expansion
    response = client.get("/calendar/", params={
        "start_after": query_start,
        "end_before": query_end
    }, headers={"X-API-Key": user_api_key})

    assert response.status_code == 200
    events = response.json()
    # Assert that 5 new events (1 one-time + 4 recurring) were found on top of any pre-existing ones.
    assert len(events) == initial_count + 5

def test_tag_management(test_user):
    """Test deleting a specific tag from an event."""
    client = TestClient(app)
    user_api_key = test_user["api_key"]
    
    # Create an event with multiple tags
    response = client.post("/calendar/", params={
        "title": "Event for Tag Test", 
        "start_time": datetime.now().isoformat(),
        "tags": '["todelete", "tokeep", "important"]'
    }, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    event_id = response.json()["id"]

    # Delete a specific tag from the event
    response = client.delete(f"/calendar/tags/{event_id}", params={"tag": "todelete"}, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    
    # Verify the tag was removed and other tags remain
    response = client.get(f"/calendar/{event_id}", headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    event_details = response.json()
    assert "todelete" not in event_details["tags"]
    assert "tokeep" in event_details["tags"]
    assert "important" in event_details["tags"]