# Test the users route of the API
 
import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import unit_test_utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'app'))
import routers.users as users
from app import app
import database
from fastapi.testclient import TestClient

@pytest.fixture(scope="module", autouse=True)
def setup_module():
    """Setup the database for the module."""
    unit_test_utils.clean_tables()

def test_create_user():
    # Create user, check if the data from the response is correct (in db and works on other endpoints)
    client = TestClient(app)
    admin_api_key = unit_test_utils.manual_admin_key_override()
    response = client.post(
        "/users/",
        headers={"X-API-Key": "faux_admin_key"}
    )
    assert response.status_code == 403  # Should fail without valid admin key
    response = client.post(
        "/users/",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    # Parse response
    data = response.json()
    user_id = data.get("user_id")
    api_key = data.get("api_key")
    # Check user in db
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("SELECT id, api_key_hash FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    assert user is not None
    assert user[0] == user_id
    assert unit_test_utils.hash_api_key(api_key) == user[1]

def test_list_users():
    client = TestClient(app)
    admin_api_key = unit_test_utils.manual_admin_key_override()

    # Get initial user count to make test independent of state from previous tests
    initial_response = client.get("/users/", headers={"X-API-Key": admin_api_key})
    assert initial_response.status_code == 200
    initial_count = len(initial_response.json())

    # Create a few extra users
    for _ in range(3):
        response = client.post(
            "/users/",
            headers={"X-API-Key": admin_api_key}
        )
        assert response.status_code == 200

    # Test with invalid key
    response = client.get(
        "/users/",
        headers={"X-API-Key": "faux_admin_key"}
    )
    assert response.status_code == 403  # Should fail without valid admin key

    # List users
    response = client.get(
        "/users/",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Assert that exactly 3 users were added to the initial count
    assert len(data) == initial_count + 3

def test_user_actions():
    # Test get, put and delete user actions
    client = TestClient(app)
    admin_api_key = unit_test_utils.manual_admin_key_override()
    # Create a user
    response = client.post(
        "/users/",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    user_id = data.get("user_id")
    api_key = data.get("api_key")
    # Get user details
    response = client.get(
        f"/users/{user_id}",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["id"] == user_id
    assert user_data["role"] == "user"
    assert "utc_offset_minutes" in user_data
    assert "created_at" in user_data
    assert "updated_at" in user_data
    # Update user role
    # Update user utc_offset_minutes with valid user API key
    new_offset = 180
    response = client.put(
        f"/users/{user_id}",
        params={"utc_offset_minutes": new_offset},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User updated successfully"
    # Check in DB
    cursor = database.get_cursor()
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute("SELECT utc_offset_minutes FROM users WHERE id = %s", (user_id,))
    db_offset = cursor.fetchone()[0]
    assert db_offset == new_offset

    # Try updating with invalid API key
    response = client.put(
        f"/users/{user_id}",
        params={"utc_offset_minutes": 60},
        headers={"X-API-Key": "invalid_key"}
    )
    assert response.status_code == 403

    # Try updating another user as non-admin (should fail)
    # Create a second user
    response = client.post(
        "/users/",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    second_user_id = response.json()["user_id"]
    # Try to update second user with first user's API key
    response = client.put(
        f"/users/{second_user_id}",
        params={"utc_offset_minutes": 90},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 403

    # Admin can update any user
    response = client.put(
        f"/users/{second_user_id}",
        params={"utc_offset_minutes": 120},
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User updated successfully"
    cursor.execute("SELECT utc_offset_minutes FROM users WHERE id = %s", (second_user_id,))
    db_offset = cursor.fetchone()[0]
    assert db_offset == 120

    # Try updating non-existent user
    response = client.put(
        "/users/nonexistent_user",
        params={"utc_offset_minutes": 30},
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200 or response.status_code == 500

    # Delete user
    response = client.delete(
        f"/users/{user_id}",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User deleted successfully"
    # Check user is deleted in DB
    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    db_user = cursor.fetchone()
    assert db_user is None

def test_reroll_api_key():
    # Test API key reroll functionality
    client = TestClient(app)
    admin_api_key = unit_test_utils.manual_admin_key_override()
    
    # Create a user
    response = client.post(
        "/users/",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    user_id = data.get("user_id")
    original_api_key = data.get("api_key")
    
    # Test user rerolling their own API key
    response = client.post(
        f"/users/{user_id}/reroll",
        headers={"X-API-Key": original_api_key}
    )
    assert response.status_code == 200
    reroll_data = response.json()
    assert reroll_data["user_id"] == user_id
    assert reroll_data["new_api_key"] != original_api_key
    assert reroll_data["message"] == "API key rerolled successfully"
    
    # Verify the new API key works
    new_api_key = reroll_data["new_api_key"]
    response = client.get(
        f"/users/{user_id}",
        headers={"X-API-Key": new_api_key}
    )
    assert response.status_code == 200
    
    # Verify the old API key no longer works
    response = client.get(
        f"/users/{user_id}",
        headers={"X-API-Key": original_api_key}
    )
    assert response.status_code == 403
    
    # Test admin rerolling API key for another user
    response = client.post(
        f"/users/{user_id}/reroll",
        headers={"X-API-Key": admin_api_key},
        params={"for_user": user_id}
    )
    assert response.status_code == 200
    admin_reroll_data = response.json()
    assert admin_reroll_data["user_id"] == user_id
    assert admin_reroll_data["new_api_key"] != new_api_key
    
    # Test admin trying to reroll their own API key (should fail)
    response = client.post(
        f"/users/admin/reroll",
        headers={"X-API-Key": admin_api_key},
        params={"for_user": "admin"}
    )
    assert response.status_code == 403  # Admin cannot reroll their own API key
    
    # Test admin trying to reroll their own API key without for_user param (should fail)
    response = client.post(
        f"/users/admin/reroll",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 403  # Admin cannot reroll their own API key
    
    # Test user trying to reroll API key for another user (should fail)
    # Create a second user
    response = client.post(
        "/users/",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    second_user_id = response.json()["user_id"]
    second_user_api_key = response.json()["api_key"]
    
    # Try to reroll first user's API key with second user's API key
    response = client.post(
        f"/users/{user_id}/reroll",
        headers={"X-API-Key": second_user_api_key}
    )
    assert response.status_code == 403
    
    # Test with invalid API key
    response = client.post(
        f"/users/{user_id}/reroll",
        headers={"X-API-Key": "invalid_key"}
    )
    assert response.status_code == 403
    
    # Test with non-existent user
    response = client.post(
        "/users/nonexistent_user/reroll",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 404