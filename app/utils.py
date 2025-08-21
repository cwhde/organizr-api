# Utility functions for the organizr api

import hashlib
import secrets
import string
import logging
import database
from dateutil import parser
import json
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
import datetime
from enum import Enum
import icalendar
import recurring_ical_events

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
        
        cursor.execute(f"USE {database.MYSQL_DATABASE}")
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
    cursor.execute(f"USE {database.MYSQL_DATABASE}")
    cursor.execute(f"SELECT user_id FROM {table_name} WHERE id = %s", (resource_id,))
    result = cursor.fetchone()

    if not result:
        raise HTTPException(status_code=404, detail=f"{resource_type.value.capitalize()} entry not found")

    if user_role != 'admin':
        entry_owner_id = result[0]
        if user_id != entry_owner_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return user_id, user_role

# RRULE Query Helpers

def _normalize_dt(val):
    """
    Normalize input to a standard datetime object.
    Args:
        val: Input value (datetime, date, ISO 8601 string)
    Returns:
        datetime.datetime: Normalized datetime object
    """
    if isinstance(val, datetime.datetime):
        return val
    if isinstance(val, datetime.date):
        return datetime.datetime.combine(val, datetime.time.min)
    if isinstance(val, str):
        dt = validate_time_format(val)
        if dt is None:
            raise HTTPException(status_code=400, detail=f"Invalid time format: {val}")
        return dt
    raise HTTPException(status_code=400, detail="Invalid time argument type")


def _event_to_ical_component(ev: Dict[str, Any]) -> Optional[icalendar.Event]:
    """
    Convert an event in the format used by Organizr to an iCalendar Event component.

    Args:
        ev (Dict[str, Any]): Event dictionary containing keys like 'start_datetime', 'end_datetime', 'rrule', etc.
    Returns:
        Optional[icalendar.Event]: iCalendar Event component or None if the event is invalid.
    """
    rrule = ev.get("rrule")
    if not rrule:
        return None
    start = ev.get("start_datetime")
    end = ev.get("end_datetime")
    if isinstance(start, str):
        start = validate_time_format(start)
    if isinstance(end, str):
        end = validate_time_format(end)
    if start is None:
        logger.warning(f"Skipping event without valid start_datetime: {ev}")
        return None
    if end is None:
        end = start
    ical_ev = icalendar.Event()
    uid = f"organizr-{ev.get('user_id', '')}-{ev.get('id', '')}"
    ical_ev.add("uid", uid)
    if ev.get("title"):
        ical_ev.add("summary", ev.get("title"))
    if ev.get("description"):
        ical_ev.add("description", ev.get("description"))
    ical_ev.add("dtstart", start)
    ical_ev.add("dtend", end)
    ical_ev.add("rrule", icalendar.prop.vRecur.from_ical(str(rrule)))
    if ev.get("id") is not None:
        ical_ev.add("ORGANIZR-ID", str(ev.get("id")))
    if ev.get("user_id") is not None:
        ical_ev.add("ORGANIZR-USER-ID", str(ev.get("user_id")))
    if ev.get("tags"):
        ical_ev.add("ORGANIZR-TAGS", json.dumps(ev.get("tags")))
    if ev.get("rrule"):
        ical_ev.add("ORGANIZR-RRULE", str(ev.get("rrule")))
    return ical_ev


def _build_ical_from_events(events: List[Dict[str, Any]]) -> icalendar.Calendar:
    """
    Builds an iCalendar Calendar from a list of single events in the format used by Organizr, by first converting each and then adding them to the calendar.

    Args:
        events (List[Dict[str, Any]]): List of events in the format used by Organizr.
    Returns:
        icalendar.Calendar: iCalendar Calendar object containing all the events.
    """
    cal = icalendar.Calendar()
    cal.add("prodid", "-//organizr//calendar//EN")
    cal.add("version", "2.0")
    for ev in events:
        try:
            comp = _event_to_ical_component(ev)
            if comp is not None:
                cal.add_component(comp)
        except Exception as ex:
            logger.warning(f"Skipping event {ev.get('id')} due to RRULE or data error: {ex}")
            continue
    return cal


def _occurrence_to_org_dict(comp) -> Dict[str, Any]:
    """
    Converts an iCalendar Event to a dictionary in the format used by Organizr.

    Args:
        comp (icalendar.Event): iCalendar Event component.
    Returns:
        Dict[str, Any]: Dictionary containing event details in the Organizr format.
    """
    occ_start = comp.get("DTSTART").dt
    occ_end = comp.get("DTEND").dt if comp.get("DTEND") else occ_start
    raw_id = comp.get("ORGANIZR-ID")
    raw_user = comp.get("ORGANIZR-USER-ID")
    raw_tags = comp.get("ORGANIZR-TAGS")
    raw_rrule = comp.get("ORGANIZR-RRULE")
    return {
        "id": int(raw_id) if raw_id is not None else None,
        "user_id": str(raw_user) if raw_user is not None else None,
        "title": str(comp.get("SUMMARY")) if comp.get("SUMMARY") else "",
        "description": str(comp.get("DESCRIPTION")) if comp.get("DESCRIPTION") else None,
        "start_datetime": occ_start,
        "end_datetime": occ_end,
        "rrule": str(raw_rrule) if raw_rrule is not None else None,
        "tags": json.loads(str(raw_tags)) if raw_tags else None,
    }

def handle_rrule_query(events_with_rrule, start_date, end_date):
    """
    Turn recurring events into iCal Formats and create an iCalendar Calendar, which is then used to query it with the given rrule.

    Args:
        events_with_rrule (List[Dict[str, Any]]): Events in Organizr format containing an 'rrule'.
        start_date (str|datetime): Start of window (ISO 8601 string or datetime).
        end_date (str|datetime): End of window (ISO 8601 string or datetime).

    Returns:
        List[Dict[str, Any]]: Occurrences in our format within the time frame.
    """
    if not events_with_rrule:
        return []

    start_dt = _normalize_dt(start_date)
    end_dt = _normalize_dt(end_date)
    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="'start_date' must be before 'end_date'")

    try:
        cal = _build_ical_from_events(events_with_rrule)
        cal_bytes = cal.to_ical()
        a_calendar = icalendar.Calendar.from_ical(cal_bytes)
        occurrences = recurring_ical_events.of(a_calendar, skip_bad_series=True).between(start_dt, end_dt)
    except HTTPException:
        raise
    except Exception as ex:
        logger.error(f"Error expanding rrules: {ex}")
        raise HTTPException(status_code=500, detail="Failed to expand recurring events")

    results = []
    for comp in occurrences:
        try:
            results.append(_occurrence_to_org_dict(comp))
        except Exception as ex:
            logger.warning(f"Failed to read occurrence: {ex}")
            continue

    results.sort(key=lambda x: (x.get("start_datetime") or datetime.datetime.min, x.get("id") or 0))
    return results

def build_query_filters(search_text=None, tags=None, status=None, match_mode="and"):
    """Build SQL conditions and params for common query filters"""
    conds, params = [], []
    
    if search_text:
        conds.append("(title LIKE %s OR description LIKE %s)")
        like = f"%{search_text}%"
        params.extend([like, like])
    
    if status is not None:
        conds.append("status = %s")
        params.append(status.value if hasattr(status, 'value') else status)
    
    if tags:
        tag_conds = []
        for t in tags:
            tag_conds.append("JSON_CONTAINS(tags, JSON_QUOTE(%s), '$')")
            params.append(t)
        joiner = " AND " if match_mode.lower() == "and" else " OR "
        conds.append(f"({joiner.join(tag_conds)})")
    
    return conds, params

def apply_match_mode_filter(items, search_text=None, tags=None, status=None, match_mode="and"):
    """Apply match_mode filtering to a list of items"""
    if not any([search_text, tags, status]):
        return items
    
    mode = match_mode.lower()
    
    def matches_item(item):
        matches = []
        
        if search_text:
            title = (item.get("title") or "").lower()
            desc = (item.get("description") or "").lower()
            matches.append(search_text.lower() in title or search_text.lower() in desc)
        
        if status is not None:
            item_status = item.get("status")
            status_val = status.value if hasattr(status, 'value') else status
            matches.append(item_status == status_val)
        
        if tags:
            item_tags = item.get("tags") or []
            if isinstance(item_tags, str):
                try:
                    item_tags = json.loads(item_tags)
                except (json.JSONDecodeError, TypeError):
                    item_tags = []
            if mode == "and":
                matches.append(all(t in item_tags for t in tags))
            else:
                matches.append(any(t in item_tags for t in tags))
        
        return all(matches) if mode == "and" else any(matches)
    
    return [item for item in items if matches_item(item)]

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
