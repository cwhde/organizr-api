# Utility functions for the organizr api

import hashlib
import secrets
import string
import logging
import database
from dateutil import parser
import json
from typing import Optional
from fastapi import HTTPException
import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class ResourceType(str, Enum):
    CALENDAR = "calendar"
    TASK = "task"
    NOTE = "note"

def generate_user_id():
    """Generate a random 8-character alphanumeric user ID"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))

def generate_api_key():
    """Generate a random API key"""
    return secrets.token_urlsafe(32)

def hash_api_key(api_key):
    """Hash an API key using SHA-256"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def validate_api_key(api_key, target_user_id=None):
    """
    Validate API key and return user info and permissions
    
    Args:
        api_key: API key to validate
        target_user_id: Optional user ID to check permissions against
    
    Returns:
        tuple: (user_id, user_role, has_permission)
        - user_id: ID of the user who owns the API key
        - user_role: Role of the user ('admin' or 'user')
        - has_permission: True if user has rights over target_user_id
    """
    try:
        cursor = database.get_cursor()
        api_key_hash = hash_api_key(api_key)
        
        cursor.execute("USE organizr")
        cursor.execute("SELECT id, role FROM users WHERE api_key_hash = %s", (api_key_hash,))
        result = cursor.fetchone()
        
        if not result:
            return None, None, False
        
        user_id, user_role = result
        
        # Check permissions
        has_permission = False
        if target_user_id is None or user_role == 'admin' or user_id == target_user_id:
            has_permission = True
        
        return user_id, user_role, has_permission
        
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        return None, None, False

def validate_user_for_action(api_key: str, for_user: Optional[str] = None):
    """
    Validates API key and permissions for a user to perform an action on another user's resources.

    Args:
        api_key (str): The API key of the user performing the action.
        for_user (Optional[str]): The ID of the user whose resources are being accessed.

    Returns:
        str: The ID of the user whose resources should be accessed.

    Raises:
        HTTPException: If validation fails.
    """
    requesting_user_id, requesting_user_role, _ = validate_api_key(api_key)

    if not requesting_user_id:
        raise HTTPException(status_code=403, detail="Invalid API key")

    if requesting_user_role == 'admin':
        if not for_user:
            raise HTTPException(status_code=400, detail="Admin must specify 'for_user' when performing this action.")
        if for_user == requesting_user_id:
            raise HTTPException(status_code=400, detail="Admin cannot perform this action on themselves.")
        return for_user

    else:  # Regular user
        if for_user and for_user != requesting_user_id:
            raise HTTPException(status_code=403, detail="Users cannot perform actions for other users.")
        return requesting_user_id

def validate_entry_access(api_key: str, resource_type: ResourceType, resource_id: int):
    """
    Validates if a user has permission to access a resource entry.

    Args:
        api_key (str): The API key of the user.
        resource_type (ResourceType): The type of the resource.
        resource_id (int): The ID of the resource entry.

    Returns:
        tuple: (user_id, user_role)

    Raises:
        HTTPException: If validation fails.
    """
    user_id, user_role, _ = validate_api_key(api_key)
    if not user_id:
        raise HTTPException(status_code=403, detail="Invalid API key")

    table_map = {
        ResourceType.CALENDAR: "calendar_entries",
        ResourceType.TASK: "tasks",
        ResourceType.NOTE: "notes",
    }
    table_name = table_map.get(resource_type)
    if not table_name:
        raise HTTPException(status_code=500, detail="Invalid resource type specified for validation.")

    cursor = database.get_cursor()
    cursor.execute("USE organizr")
    cursor.execute(f"SELECT user_id FROM {table_name} WHERE id = %s", (resource_id,))
    result = cursor.fetchone()

    if not result:
        raise HTTPException(status_code=404, detail=f"{resource_type.value.capitalize()} entry not found")

    if user_role != 'admin':
        entry_owner_id = result[0]
        if user_id != entry_owner_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return user_id, user_role

def handle_rrule_query(events_with_rrule, start_date, end_date):
    """
    Handles querying of events with rrules within a specific time range.
    Currently, this is a placeholder and will raise an error.
    """
    if events_with_rrule:
        raise HTTPException(status_code=501, detail="Querying events with recurrence rules (rrule) within a specific time range is not yet supported.")
    return []

def list_to_json(lst):
    """
    Convert a list to a JSON string

    Args:
        lst: List to convert

    Returns:
        str: JSON string representation of the list
    """
    return json.dumps(lst) if lst else None

def validate_time_format(time_str):
    """
    Validate time format (ISO 8601) and return as datetime object

    Args:
        time_str: Time string to validate

    Returns:
        datetime: Parsed datetime object if valid, None otherwise
    """
    try:
        return parser.isoparse(time_str)
    except ValueError:
        logger.error(f"Invalid time format: {time_str}")
        return None
