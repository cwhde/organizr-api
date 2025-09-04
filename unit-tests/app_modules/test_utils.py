# Test the shared utility module of the API

import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
from fastapi import HTTPException
from utils import *
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from unit_test_utils import setup_test_user, cleanup_test_users, create_test_calendar_entry

@pytest.fixture(autouse=True)
def setup_teardown():
    user_id, api_key, admin_id, admin_key = setup_test_user()
    yield user_id, api_key, admin_id, admin_key
    cleanup_test_users()

def test_generate_user_id():
    uid = generate_user_id()
    assert len(uid) == 8 and uid.isalnum()

def test_generate_api_key():
    key = generate_api_key()
    assert len(key) > 20

def test_hash_api_key():
    hashed = hash_api_key("test")
    assert len(hashed) == 64

def test_validate_api_key(setup_teardown):
    user_id, api_key, _, _ = setup_teardown
    uid, role, perm = validate_api_key(api_key)
    assert uid == user_id and role == "user" and perm
    uid, role, perm = validate_api_key("invalid")
    assert not uid and not role and not perm

def test_validate_user_for_action(setup_teardown):
    user_id, api_key, admin_id, admin_key = setup_teardown
    result = validate_user_for_action(api_key)
    assert result == user_id
    
    # Test admin without for_user (line 93-94)
    with pytest.raises(HTTPException, match="Admin must specify"):
        validate_user_for_action(admin_key, "")
    
    # Test admin acting on themselves (line 95-96) 
    with pytest.raises(HTTPException, match="Admin cannot perform"):
        validate_user_for_action(admin_key, admin_id)
    
    # Test user trying to act for another user (line 100)
    with pytest.raises(HTTPException, match="Users cannot perform"):
        validate_user_for_action(api_key, admin_id)
    
    with pytest.raises(HTTPException):
        validate_user_for_action("invalid")

def test_validate_entry_access(setup_teardown):
    user_id, api_key, admin_id, _ = setup_teardown
    entry_id = create_test_calendar_entry(user_id)
    uid, _ = validate_entry_access(api_key, ResourceType.CALENDAR, entry_id)
    assert uid == user_id
    
    # Test invalid resource type (line 129)
    with pytest.raises(HTTPException, match="Invalid resource type"):
        validate_entry_access(api_key, "INVALID", entry_id)
    
    # Test entry not found (line 137)
    with pytest.raises(HTTPException, match="entry not found"):
        validate_entry_access(api_key, ResourceType.CALENDAR, 99999)
    
    # Test access denied - user accessing another user's entry (line 142)
    other_entry = create_test_calendar_entry(admin_id)
    with pytest.raises(HTTPException, match="Access denied"):
        validate_entry_access(api_key, ResourceType.CALENDAR, other_entry)
    
    with pytest.raises(HTTPException):
        validate_entry_access("invalid", ResourceType.CALENDAR, entry_id)

def test_handle_rrule_query():
    result = handle_rrule_query([], None, None)
    assert result == []
    with pytest.raises(HTTPException):
        handle_rrule_query([{"rrule": "test"}], None, None)

def test_list_to_json():
    assert list_to_json(["a", "b"]) == '["a", "b"]'
    assert list_to_json(None) is None
    with pytest.raises(TypeError):
        list_to_json(set([1, 2, 3]))

def test_validate_time_format():
    assert validate_time_format("2023-01-01T10:00:00")
    assert validate_time_format("invalid") is None