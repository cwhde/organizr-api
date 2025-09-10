# Test the apps route of the API

import pytest
import sys
import os
from fastapi.testclient import TestClient

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

def test_app_crud_and_auth():
    """Test creating, listing, updating, and deleting an app, including auth checks."""
    client = TestClient(app)
    admin_api_key = unit_test_utils.manual_admin_key_override()
    app_name = "test-app"
    updated_app_name = "test-app-updated"

    # --- Test without auth ---
    response = client.post("/apps/", json={"name": app_name}, headers={"X-API-Key": "bad-key"})
    assert response.status_code == 403

    # --- Test with auth ---
    # Create app
    response = client.post("/apps/", json={"name": app_name}, headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == app_name
    app_id = data["id"]

    # Check in DB
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("SELECT id, name FROM apps WHERE id = %s", (app_id,))
    db_app = cursor.fetchone()
    assert db_app is not None
    assert db_app[1] == app_name

    # List apps
    response = client.get("/apps/", headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    apps_list = response.json()
    assert isinstance(apps_list, list)
    assert any(a['name'] == app_name for a in apps_list)

    # Update app
    response = client.put(f"/apps/{app_name}", json={"name": updated_app_name}, headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    assert response.json()["name"] == updated_app_name

    # Check update in DB
    cursor.execute("SELECT name FROM apps WHERE id = %s", (app_id,))
    assert cursor.fetchone()[0] == updated_app_name

    # Test updating non-existent app
    response = client.put("/apps/non-existent", json={"name": "new"}, headers={"X-API-Key": admin_api_key})
    assert response.status_code == 404

    # Delete app
    response = client.delete(f"/apps/{updated_app_name}", headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    assert response.json()["message"] == "App deleted successfully"

    # Check deletion in DB
    cursor.execute("SELECT id FROM apps WHERE id = %s", (app_id,))
    assert cursor.fetchone() is None

    # Test deleting non-existent app
    response = client.delete("/apps/non-existent", headers={"X-API-Key": admin_api_key})
    assert response.status_code == 404

def test_app_user_links_and_translation():
    """Test linking users, listing links, translating IDs, and deleting links."""
    client = TestClient(app)
    admin_api_key = unit_test_utils.manual_admin_key_override()
    
    # --- Setup: Create an app and a user ---
    app_name = "link-test-app"
    client.post("/apps/", json={"name": app_name}, headers={"X-API-Key": admin_api_key})

    user_response = client.post("/users/", headers={"X-API-Key": admin_api_key})
    user_id = user_response.json()["user_id"]
    external_id = "discord-12345"

    # --- Test User Link CRUD ---
    # Create user link
    link_payload = {"user_id": user_id, "external_id": external_id}
    response = client.post(f"/apps/{app_name}/users", json=link_payload, headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    link_data = response.json()
    assert link_data["user_id"] == user_id
    assert link_data["external_id"] == external_id

    # Test creating duplicate link (should fail)
    response = client.post(f"/apps/{app_name}/users", json=link_payload, headers={"X-API-Key": admin_api_key})
    assert response.status_code == 409

    # List user links for the app
    response = client.get(f"/apps/{app_name}/users", headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    links_list = response.json()
    assert any(l['external_id'] == external_id for l in links_list)

    # --- Test ID Translation ---
    # Translate external to internal
    response = client.get(f"/apps/{app_name}/translate", params={"external_id": external_id}, headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    assert response.json()["user_id"] == user_id

    # Translate internal to external
    response = client.get(f"/apps/{app_name}/translate", params={"user_id": user_id}, headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    assert response.json()["external_id"] == external_id

    # Test translation with both params (should fail)
    response = client.get(f"/apps/{app_name}/translate", params={"user_id": user_id, "external_id": external_id}, headers={"X-API-Key": admin_api_key})
    assert response.status_code == 400

    # Test translation for non-existent user
    response = client.get(f"/apps/{app_name}/translate", params={"external_id": "non-existent"}, headers={"X-API-Key": admin_api_key})
    assert response.status_code == 404

    # --- Test Deletion ---
    # Delete user link
    response = client.delete(f"/apps/{app_name}/users/{external_id}", headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    assert response.json()["message"] == "User link deleted successfully"

    # Verify deletion in DB
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("SELECT id FROM app_user_links WHERE external_id = %s", (external_id,))
    assert cursor.fetchone() is None