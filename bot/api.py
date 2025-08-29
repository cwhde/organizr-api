# api.py

import os
import logging
import json
import requests
from typing import List, Optional

# --- Environment Variables ---
organizr_key = os.environ.get('ORGANIZR_API_KEY')
organizr_baseurl = os.environ.get('ORGANIZR_BASE_URL')

logger = logging.getLogger(__name__)

# --- Tool Definitions for LLM ---
functions = [
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": "Creates a new note with a title and content. Can optionally include tags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The title of the new note."},
                    "content": {"type": "string", "description": "The main content of the new note."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "A list of tags to associate with the note, e.g., ['work', 'project-x']."}
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_notes",
            "description": "Searches for and retrieves notes. You can filter by ID, title, content, or tags. Leave all filters empty to get all notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "integer", "description": "The unique ID of a specific note to retrieve."},
                    "title": {"type": "string", "description": "A search term to find in note titles."},
                    "content": {"type": "string", "description": "A search term to find in note content."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "A list of tags to filter by. Notes must have at least one of these tags."},
                    "match_mode": {"type": "string", "enum": ["and", "or"], "description": "How to combine filters. 'and' means all conditions must be met, 'or' means any condition can be met. Defaults to 'and'."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_note",
            "description": "Updates an existing note identified by its ID. You only need to provide the fields you want to change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "integer", "description": "The ID of the note to update."},
                    "new_title": {"type": "string", "description": "The new title for the note."},
                    "new_content": {"type": "string", "description": "The new content for the note. This will completely replace the old content."},
                    "new_tags": {"type": "array", "items": {"type": "string"}, "description": "The new list of tags. This will replace the old list of tags."}
                },
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": "Deletes a specific note identified by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "integer", "description": "The ID of the note to delete."},
                },
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Creates a new task. A title is required, but other fields are optional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The title of the task."},
                    "description": {"type": "string", "description": "A detailed description of the task."},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"], "description": "The status of the task. Defaults to 'pending'."},
                    "due_date": {"type": "string", "description": "The due date and time for the task in ISO 8601 format (e.g., '2025-12-31T23:59:59')."},
                    "rrule": {"type": "string", "description": "An iCalendar RRULE string for recurring tasks, e.g., 'FREQ=WEEKLY;BYDAY=MO'."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "A list of tags for the task."}
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "Searches for and retrieves tasks based on various filters like search text, tags, status, or due date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_text": {"type": "string", "description": "Text to search for in the task's title and description."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "A list of tags to filter tasks by."},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"], "description": "Filter tasks by their status."},
                    "due_after": {"type": "string", "description": "Retrieve tasks due after this ISO 8601 date/time."},
                    "due_before": {"type": "string", "description": "Retrieve tasks due before this ISO 8601 date/time."},
                    "match_mode": {"type": "string", "enum": ["and", "or"], "description": "How to combine filters. 'and' means all conditions must be met, 'or' means any condition can be met. Defaults to 'and'."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Updates an existing task identified by its ID. Provide only the fields you want to change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "The ID of the task to update."},
                    "title": {"type": "string", "description": "The new title for the task."},
                    "description": {"type": "string", "description": "The new description for the task."},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"], "description": "The new status for the task."},
                    "due_date": {"type": "string", "description": "The new due date in ISO 8601 format."},
                    "rrule": {"type": "string", "description": "An iCalendar RRULE string for recurring tasks, e.g., 'FREQ=DAILY;COUNT=5'."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "The new list of tags, which will replace the old list."}
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Deletes a task by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "The ID of the task to delete."},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "Creates a new calendar event. A title and a start time are required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The title of the calendar event."},
                    "start_time": {"type": "string", "description": "The start date and time in ISO 8601 format (e.g., '2025-10-26T10:00:00')."},
                    "end_time": {"type": "string", "description": "The end date and time in ISO 8601 format. If not provided, it will be the same as the start time."},
                    "description": {"type": "string", "description": "A detailed description of the event."},
                    "rrule": {"type": "string", "description": "An iCalendar RRULE string for recurring events, e.g., 'FREQ=WEEKLY;BYDAY=MO'."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "A list of tags for the event."}
                },
                "required": ["title", "start_time"],
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "get_event_by_id",
            "description": "Retrieves a single, specific calendar event by its unique ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "The unique ID of the calendar event to retrieve."},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_events",
            "description": "Searches for calendar events based on filters like a date range, search text, or tags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_text": {"type": "string", "description": "Text to search for in the event's title and description."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "A list of tags to filter events by."},
                    "start_after": {"type": "string", "description": "Retrieve events that start after this ISO 8601 date/time."},
                    "end_before": {"type": "string", "description": "Retrieve events that end before this ISO 8601 date/time."},
                    "match_mode": {"type": "string", "enum": ["and", "or"], "description": "How to combine filters. 'and' means all conditions must be met, 'or' means any condition can be met. Defaults to 'and'."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_event",
            "description": "Updates an existing calendar event identified by its ID. Provide only the fields to change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "The ID of the event to update."},
                    "title": {"type": "string", "description": "The new title for the event."},
                    "start_time": {"type": "string", "description": "The new start time in ISO 8601 format."},
                    "end_time": {"type": "string", "description": "The new end time in ISO 8601 format."},
                    "description": {"type": "string", "description": "The new description for the event."},
                    "rrule": {"type": "string", "description": "An iCalendar RRULE string for recurring events, e.g., 'FREQ=YEARLY'."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "The new list of tags, replacing the old one."}
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": "Deletes a calendar event by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "The ID of the event to delete."},
                },
                "required": ["event_id"],
            },
        },
    },
]

# --- Helper Function for API Calls ---
def _request(method, endpoint, **kwargs):
    """A generic wrapper for making requests to the organizr API."""
    try:
        headers = kwargs.pop('headers', {})
        headers['accept'] = 'application/json'
        headers['X-API-Key'] = organizr_key
        
        url = f"{organizr_baseurl}{endpoint}"
        
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        
        if response.status_code == 204 or not response.content:
            return {"status": "success", "message": "Operation completed successfully."}
            
        return response.json()
    except requests.exceptions.HTTPError as e:
        try:
            error_detail = e.response.json().get("detail", str(e))
        except json.JSONDecodeError:
            error_detail = e.response.text
        logger.error(f"HTTP error calling {method} {endpoint}: {e.response.status_code} - {error_detail}")
        return {"status": "error", "message": f"API Error: {error_detail}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception calling {method} {endpoint}: {e}")
        return {"status": "error", "message": f"Connection Error: {e}"}

# --- Bot Background Functions (not exposed to LLM) ---

def check_health():
    try:
        response = requests.get(f"{organizr_baseurl}/health", headers={'accept': 'application/json'})
        return response.json().get("status") == "ok"
    except requests.exceptions.RequestException as e:
        logger.error(f"Health check failed: {e}")
        return False

def list_apps():
    return _request("get", "/apps/")
    
def create_app(name="organizrbot"):
    return _request("post", "/apps/", json={"name": name})

def check_user_exists_in_app(externalId):
    users = _request("get", "/apps/organizrbot/users")
    if isinstance(users, list):
        return any(user.get('external_id') == str(externalId) for user in users)
    return False

def create_and_link_user(externalId):
    user_data = _request("post", "/users/")
    if user_data and "user_id" in user_data:
        user_id = user_data["user_id"]
        link_data = {"user_id": user_id, "external_id": str(externalId)}
        return _request("post", "/apps/organizrbot/users", json=link_data)
    else:
        logger.error(f"Failed to create internal user for externalId {externalId}. Response: {user_data}")
        return {"status": "error", "message": "Failed to create internal API user."}

def id_to_internal(externalId):
    response = _request("get", f"/apps/organizrbot/translate", params={"external_id": str(externalId)})
    return response.get("user_id") if response and "user_id" in response else None

# --- API Wrapper Functions for LLM Tools ---

# NOTES
def create_note(for_user: str, title: str, content: str, tags: Optional[List[str]] = None):
    payload = {"title": title, "content": content, "tags": tags or []}
    return _request("post", "/notes/", params={"for_user": for_user}, json=payload)

def get_notes(for_user: str, note_id: Optional[int] = None, title: Optional[str] = None, content: Optional[str] = None, tags: Optional[List[str]] = None, match_mode: str = "and"):
    params = {"for_user": for_user, "match_mode": match_mode}
    if note_id: params['note_id'] = note_id
    if title: params['title'] = title
    if content: params['content'] = content
    if tags: params['tags'] = tags
    return _request("get", "/notes/", params=params)

def update_note(note_id: int, new_title: Optional[str] = None, new_content: Optional[str] = None, new_tags: Optional[List[str]] = None, for_user: Optional[str] = None):
    payload = {}
    if new_title is not None: payload['title'] = new_title
    if new_content is not None: payload['content'] = new_content
    if new_tags is not None: payload['tags'] = new_tags
    if not payload: return {"status": "info", "message": "No fields provided to update."}
    return _request("put", f"/notes/{note_id}", json=payload)

def delete_note(note_id: int, for_user: Optional[str] = None):
    return _request("delete", f"/notes/{note_id}")

# TASKS
def create_task(for_user: str, title: str, description: Optional[str] = None, status: str = "pending", due_date: Optional[str] = None, rrule: Optional[str] = None, tags: Optional[List[str]] = None):
    params = {"for_user": for_user, "title": title, "status": status}
    if description: params['description'] = description
    if due_date: params['due_date'] = due_date
    if rrule: params['rrule'] = rrule
    if tags: params['tags'] = tags
    return _request("post", "/tasks/", params=params)

def get_tasks(for_user: str, search_text: Optional[str] = None, tags: Optional[List[str]] = None, status: Optional[str] = None, due_after: Optional[str] = None, due_before: Optional[str] = None, match_mode: str = "and"):
    params = {"for_user": for_user, "match_mode": match_mode}
    if search_text: params['search_text'] = search_text
    if tags: params['tags'] = tags
    if status: params['status'] = status
    if due_after: params['due_after'] = due_after
    if due_before: params['due_before'] = due_before
    return _request("get", "/tasks/", params=params)
    
def update_task(task_id: int, title: Optional[str] = None, description: Optional[str] = None, status: Optional[str] = None, due_date: Optional[str] = None, rrule: Optional[str] = None, tags: Optional[List[str]] = None, for_user: Optional[str] = None):
    params = {}
    if title: params['title'] = title
    if description: params['description'] = description
    if status: params['status'] = status
    if due_date: params['due_date'] = due_date
    if rrule: params['rrule'] = rrule
    if tags: params['tags'] = tags
    if not params: return {"status": "info", "message": "No fields provided to update."}
    return _request("put", f"/tasks/{task_id}", params=params)

def delete_task(task_id: int, for_user: Optional[str] = None):
    return _request("delete", f"/tasks/{task_id}")

# CALENDAR
def create_event(for_user: str, title: str, start_time: str, end_time: Optional[str] = None, description: Optional[str] = None, rrule: Optional[str] = None, tags: Optional[List[str]] = None):
    params = {"for_user": for_user, "title": title, "start_time": start_time}
    if end_time: params['end_time'] = end_time
    if description: params['description'] = description
    if rrule: params['rrule'] = rrule
    if tags: params['tags'] = tags
    return _request("post", "/calendar/", params=params)

def get_event_by_id(event_id: int, for_user: Optional[str] = None):
    return _request("get", f"/calendar/{event_id}")
    
def query_events(for_user: str, search_text: Optional[str] = None, tags: Optional[List[str]] = None, start_after: Optional[str] = None, end_before: Optional[str] = None, match_mode: str = "and"):
    params = {"for_user": for_user, "match_mode": match_mode}
    if search_text: params['search_text'] = search_text
    if tags: params['tags'] = tags
    if start_after: params['start_after'] = start_after
    if end_before: params['end_before'] = end_before
    return _request("get", "/calendar/", params=params)

def update_event(event_id: int, title: Optional[str] = None, start_time: Optional[str] = None, end_time: Optional[str] = None, description: Optional[str] = None, rrule: Optional[str] = None, tags: Optional[List[str]] = None, for_user: Optional[str] = None):
    params = {}
    if title: params['title'] = title
    if start_time: params['start_time'] = start_time
    if end_time: params['end_time'] = end_time
    if description: params['description'] = description
    if rrule: params['rrule'] = rrule
    if tags: params['tags'] = tags
    if not params: return {"status": "info", "message": "No fields provided to update."}
    return _request("put", f"/calendar/{event_id}", params=params)

def delete_event(event_id: int, for_user: Optional[str] = None):
    return _request("delete", f"/calendar/{event_id}")