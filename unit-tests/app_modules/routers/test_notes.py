# Test the notes route of the API

import pytest
import sys
import os
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import unit_test_utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'app'))
import database
from app import app

@pytest.fixture(scope="module", autouse=True)
def setup_module():
    """Setup the database for the module."""
    unit_test_utils.clean_tables()

def _clear_notes_table():
    """Wipes the notes table for a clean test slate."""
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("DELETE FROM notes")
    database.get_connection().commit()

@pytest.fixture(scope="module")
def test_user():
    """Create a user for the tests in this module."""
    client = TestClient(app)
    admin_api_key = unit_test_utils.manual_admin_key_override()
    response = client.post("/users/", headers={"X-API-Key": admin_api_key})
    data = response.json()
    return {"user_id": data["user_id"], "api_key": data["api_key"]}

def test_note_crud(test_user):
    """Test creating, getting, updating, and deleting a note."""
    client = TestClient(app)
    user_api_key = test_user["api_key"]
    note_payload = {
        "title": "My First Note",
        "content": "This is some important content.",
        "tags": ["testing", "important"]
    }

    # Create note
    response = client.post("/notes/", json=note_payload, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    created_note = response.json()
    note_id = created_note["id"]
    assert created_note["title"] == note_payload["title"]
    assert created_note["tags"] == note_payload["tags"]

    # Get the specific note by ID
    response = client.get(f"/notes/", params={"note_id": note_id}, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    fetched_note = response.json()[0]
    assert fetched_note["id"] == note_id
    assert fetched_note["content"] == note_payload["content"]
    
    # Update the note
    update_payload = {"title": "Updated Title", "content": "Updated content."}
    response = client.put(f"/notes/{note_id}", json=update_payload, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    updated_note = response.json()
    assert updated_note["title"] == update_payload["title"]
    assert updated_note["content"] == update_payload["content"]

    # Check update in DB
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("SELECT title, content FROM notes WHERE id = %s", (note_id,))
    db_note = cursor.fetchone()
    assert db_note[0] == update_payload["title"]
    assert db_note[1] == update_payload["content"]

    # Delete the note
    response = client.delete(f"/notes/{note_id}", headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    assert response.json()["message"] == "Note deleted successfully"

    # Verify it's gone
    response = client.get(f"/notes/", params={"note_id": note_id}, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    assert len(response.json()) == 0

def test_query_notes(test_user):
    """Test various filtering options for getting notes."""
    _clear_notes_table() # Ensure a clean slate for this test
    client = TestClient(app)
    user_api_key = test_user["api_key"]

    # Create some notes to query
    client.post("/notes/", json={"title": "Shopping List", "content": "Milk, Bread, Cheese", "tags": ["home", "food"]}, headers={"X-API-Key": user_api_key})
    client.post("/notes/", json={"title": "Project Ideas", "content": "Build a cool app", "tags": ["work", "ideas"]}, headers={"X-API-Key": user_api_key})
    client.post("/notes/", json={"title": "Recipe for Pasta", "content": "Pasta, Tomatoes, Cheese", "tags": ["food", "recipe"]}, headers={"X-API-Key": user_api_key})

    # Query by title
    response = client.get("/notes/", params={"title": "Project"}, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Project Ideas"

    # Query by content
    response = client.get("/notes/", params={"content": "Cheese"}, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    assert len(response.json()) == 2

    # Query by a single tag
    response = client.get("/notes/", params={"tags": ["work"]}, headers={"X-API-Key": user_api_key})
    assert response.status_code == 200
    assert len(response.json()) == 1