# Test the tasks route of the API

import pytest
import sys
import os
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import unit_test_utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'app'))
import database
from app import app
import schemas

@pytest.fixture(scope="module", autouse=True)
def setup_module():
    """Setup the database for the module."""
    unit_test_utils.clean_tables()

@pytest.fixture(scope="module")
def test_user():
    """Create a user for the tests in this module."""
    client = TestClient(app)
    admin_api_key = unit_test_utils.manual_admin_key_override()
    response = client.post("/users/", headers={"X-API-Key": admin_api_key})
    data = response.json()
    return {"user_id": data["user_id"], "api_key": data["api_key"]}

def _clear_tasks_table():
    """Wipes the tasks table for a clean test slate."""
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("DELETE FROM tasks")
    database.get_connection().commit()

def test_task_crud(test_user):
    """Test basic create, read, update, delete for a task."""
    client = TestClient(app)
    user_api_key = test_user["api_key"]
    now = datetime.now().isoformat()
    
    # Create task
    response = client.post("/tasks/", params={
        "title": "My First Task", 
        "description": "Do something important",
        "due_date": now,
        "tags": ["work"]
    }, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    
    # We need to query to get the ID
    query_response = client.get("/tasks/", params={"search_text": "My First Task"}, headers={"X-API-Key": user_api_key})
    assert query_response.status_code == 200
    task_id = query_response.json()[0]['id']

    # Get by ID
    response = client.get(f"/tasks/{task_id}", headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    fetched_task = response.json()
    assert fetched_task["id"] == task_id
    assert fetched_task["title"] == "My First Task"

    # Update task
    response = client.put(f"/tasks/{task_id}", params={"status": schemas.TaskStatus.COMPLETED.value}, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    assert response.json()["status"] == schemas.TaskStatus.COMPLETED.value

    # Delete task
    response = client.delete(f"/tasks/{task_id}", headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    
    # Verify deletion
    response = client.get(f"/tasks/{task_id}", headers={"X-API-Key": user_api_key})
    assert response.status_code == 404

def test_query_tasks_with_rrule(test_user):
    """Test querying tasks, especially recurring ones."""
    _clear_tasks_table() # Ensure a clean slate for this test
    client = TestClient(app)
    user_api_key = test_user["api_key"]

    start_date = datetime.now()

    # Create a non-recurring task
    client.post("/tasks/", params={
        "title": "One-time Task",
        "due_date": (start_date + timedelta(days=1)).isoformat()
    }, headers={"X-API-Key": user_api_key})

    # Create a recurring task (every day for 5 days)
    rrule = "FREQ=DAILY;COUNT=5"
    client.post("/tasks/", params={
        "title": "Daily Standup",
        "due_date": start_date.isoformat(),
        "rrule": rrule,
        "tags": ["recurring", "work"]
    }, headers={"X-API-Key": user_api_key})

    # --- Test Queries ---
    # Query for all tasks in the next 10 days
    query_start = (start_date - timedelta(days=1)).isoformat()
    query_end = (start_date + timedelta(days=10)).isoformat()

    response = client.get("/tasks/", params={
        "due_after": query_start,
        "due_before": query_end
    }, headers={"X-API-Key": user_api_key})

    assert response.status_code == 200
    tasks = response.json()
    # Expect 1 one-time task + 5 occurrences of the daily task
    assert len(tasks) == 6

    # Query for recurring tasks by tag
    response = client.get("/tasks/", params={
        "tags": ["recurring"],
        "due_after": query_start,
        "due_before": query_end
    }, headers={"X-API-Key": user_api_key})

    assert response.status_code == 200
    recurring_tasks = response.json()
    assert len(recurring_tasks) == 5