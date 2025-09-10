# Calendar route of the API, similar in its logic to tasks

import logging
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List, Dict, Any
import database
import utils
import datetime
import schemas
import json

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=schemas.CalendarEventCreate)
async def create_event(
        title: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        rrule: Optional[str] = None,
        tags: Optional[List[str]] = None,
        for_user: Optional[str] = None, # Let admin create events for other users
        api_key: str = Header(..., alias="X-API-Key"),
):
    """Create a new calendar event"""
    target_user_id = utils.validate_user_for_action(api_key, for_user)

    # Validate time format
    try:
        start_time_parsed = utils.validate_time_format(start_time)
        if end_time:
            end_time_parsed = utils.validate_time_format(end_time)
        else:
            end_time_parsed = None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid time format: {e}")

    # Insert event into database
    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Generate new event with all given parameters, handle optional fields
        tags_json = utils.list_to_json(tags) if tags else None

        # Use start_time for end_time if not provided
        end_time_actual = end_time_parsed if end_time_parsed else start_time_parsed

        # Prepare the SQL statement with placeholders
        insert_query = """
            INSERT INTO calendar_entries 
            (user_id, title, description, start_datetime, end_datetime, rrule, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        # Execute with parameters, handling optional fields
        cursor.execute(insert_query, (
            target_user_id,
            title,
            description,
            start_time_parsed,
            end_time_actual,
            rrule,
            tags_json
        ))

        # Get the newly created event ID
        event_id = cursor.lastrowid
        database.get_connection().commit()

        logger.info(f"Created calendar entry '{title}' for user {target_user_id} with ID {event_id}")

        # Return the created event
        return {
            "id": event_id,
            "user_id": target_user_id,
            "title": title,
            "description": description,
            "start_datetime": start_time,
            "end_datetime": end_time,
            "rrule": rrule,
            "tags": tags
        }
    except Exception as e:
        database.get_connection().rollback()
        logger.error(f"Failed to create calendar entry: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create calendar entry: {str(e)}")

@router.get("/", response_model=List[schemas.CalendarEvent])
async def query_events(
        search_text: Optional[str] = None,
        tags: Optional[List[str]] = None,
        start_after: Optional[str] = None,
        end_before: Optional[str] = None,
        match_mode: Optional[str] = "and",
        for_user: Optional[str] = None,
        api_key: str = Header(..., alias="X-API-Key"),
):
    """Query calendar events by text, tags, and/or time range with configurable match mode"""
    requester_id = utils.validate_user_for_action(api_key, for_user)

    if not any([search_text, tags, start_after, end_before]):
        raise HTTPException(status_code=400, detail="At least one query filter must be provided.")

    # Parse time window
    start_dt = datetime.datetime.min
    end_dt = datetime.datetime.max
    if start_after:
        start_dt = utils.validate_time_format(start_after)
        if start_dt is None:
            raise HTTPException(status_code=400, detail="Invalid start_after time format")
    if end_before:
        end_dt = utils.validate_time_format(end_before)
        if end_dt is None:
            raise HTTPException(status_code=400, detail="Invalid end_before time format")
    
    has_time_window = bool(start_after or end_before)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        results = []

        # Non-recurring events via SQL
        base_conds = ["user_id = %s", "(rrule IS NULL OR rrule = '')", 
                     "start_datetime <= %s AND COALESCE(end_datetime, start_datetime) >= %s"]
        base_params = [requester_id, end_dt, start_dt]
        
        # For AND mode, add all filters to SQL; for OR mode, query all and filter after
        if match_mode.lower() == "and":
            tt_conds, tt_params = utils.build_query_filters(search_text, tags)
            base_conds.extend(tt_conds)
            base_params.extend(tt_params)

        sql = f"SELECT id, user_id, title, description, start_datetime, end_datetime, rrule, tags FROM calendar_entries WHERE {' AND '.join(base_conds)}"
        cursor.execute(sql, tuple(base_params))
        
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        items = []
        for row in rows:
            item = {col: row[i] for i, col in enumerate(cols)}
            if isinstance(item.get("tags"), str):
                try:
                    item["tags"] = json.loads(item["tags"])
                except (json.JSONDecodeError, TypeError):
                    item["tags"] = []
            items.append(item)
        
        if match_mode.lower() == "or":
            items = utils.apply_match_mode_filter(items, search_text, tags, None, match_mode)
        
        results.extend(items)

        # Recurring events are more complex due to rrule expansion, cant handle in sql with other entries
        if has_time_window:
            # Get recurring events and expand
            rec_conds = ["user_id = %s", "(rrule IS NOT NULL AND rrule <> '')", "start_datetime <= %s"]
            rec_params = [requester_id, end_dt]
            
            if match_mode.lower() == "and":
                rec_conds.extend(tt_conds)
                rec_params.extend(tt_params)

            sql_rec = f"SELECT id, user_id, title, description, start_datetime, end_datetime, rrule, tags FROM calendar_entries WHERE {' AND '.join(rec_conds)}"
            cursor.execute(sql_rec, tuple(rec_params))
            
            rec_rows = cursor.fetchall()
            rec_events = []
            for row in rec_rows:
                ev = {col: row[i] for i, col in enumerate(cols)}
                if isinstance(ev.get("tags"), str):
                    try:
                        ev["tags"] = json.loads(ev["tags"])
                    except (json.JSONDecodeError, TypeError):
                        ev["tags"] = []
                rec_events.append(ev)
            
            occurrences = utils.handle_rrule_query(rec_events, start_dt, end_dt)
            
            if match_mode.lower() == "or":
                occurrences = utils.apply_match_mode_filter(occurrences, search_text, tags, None, match_mode)
            
            results.extend(occurrences)
        else:
            # No time window - return base recurring rows
            rec_conds = ["user_id = %s", "(rrule IS NOT NULL AND rrule <> '')"]
            rec_params = [requester_id]
            
            if match_mode.lower() == "and":
                rec_conds.extend(tt_conds)
                rec_params.extend(tt_params)

            sql_rec = f"SELECT id, user_id, title, description, start_datetime, end_datetime, rrule, tags FROM calendar_entries WHERE {' AND '.join(rec_conds)}"
            cursor.execute(sql_rec, tuple(rec_params))
            
            rec_rows = cursor.fetchall()
            rec_items = []
            for row in rec_rows:
                item = {col: row[i] for i, col in enumerate(cols)}
                if isinstance(item.get("tags"), str):
                    try:
                        item["tags"] = json.loads(item["tags"])
                    except (json.JSONDecodeError, TypeError):
                        item["tags"] = []
                rec_items.append(item)
            
            if match_mode.lower() == "or":
                rec_items = utils.apply_match_mode_filter(rec_items, search_text, tags, None, match_mode)
            
            results.extend(rec_items)

        results.sort(key=lambda x: (x.get("start_datetime") or datetime.datetime.min, x.get("id") or 0))
        logger.info(f"Found {len(results)} events for user {requester_id}")
        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query calendar entries: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to query calendar entries: {str(e)}")


@router.get("/{entry_id}", response_model=schemas.CalendarEvent)
async def get_event(
    entry_id: int,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Get a single calendar entry"""
    utils.validate_entry_access(api_key, utils.ResourceType.CALENDAR, entry_id)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Get the event from the database
        cursor.execute("SELECT id, user_id, title, description, start_datetime, end_datetime, rrule, tags FROM calendar_entries WHERE id = %s", (entry_id,))
        event_row = cursor.fetchone()

        if not event_row:
            raise HTTPException(status_code=404, detail="Event not found")

        # Convert database row to dictionary for robust access
        columns = [desc[0] for desc in cursor.description]
        event = dict(zip(columns, event_row))

        # Parse JSON tags field
        tags_json = event.get("tags")
        if tags_json:
            try:
                event["tags"] = json.loads(tags_json)
            except (json.JSONDecodeError, TypeError):
                event["tags"] = []
        else:
            event["tags"] = []

        return event

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Failed to retrieve calendar entry {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve calendar entry {entry_id}: {str(e)}")

@router.put("/{event_id}", response_model=schemas.CalendarEvent)
async def update_event(
    event_id: int,
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    rrule: Optional[str] = None,
    tags: Optional[List[str]] = None,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Update an existing calendar event"""
    # Validate user has access to this calendar entry
    requester_id = utils.validate_entry_access(api_key, utils.ResourceType.CALENDAR, event_id)

    # Validate time formats if provided
    start_time_parsed = None
    end_time_parsed = None

    if start_time:
        try:
            start_time_parsed = utils.validate_time_format(start_time)
        except ValueError as e:
            logger.error(f"Invalid start time format: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")

    if end_time:
        try:
            end_time_parsed = utils.validate_time_format(end_time)
        except ValueError as e:
            logger.error(f"Invalid end time format: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # First get the current entry to know what fields to update
        cursor.execute("SELECT * FROM calendar_entries WHERE id = %s", (event_id,))
        current_event = cursor.fetchone()

        if not current_event:
            logger.error(f"Calendar entry {event_id} not found")
            raise HTTPException(status_code=404, detail="Calendar entry not found")

        # Prepare update values
        update_fields = []
        update_values = []

        if title is not None:
            update_fields.append("title = %s")
            update_values.append(title)

        if start_time_parsed is not None:
            update_fields.append("start_datetime = %s")
            update_values.append(start_time_parsed)

        if end_time_parsed is not None:
            update_fields.append("end_datetime = %s")
            update_values.append(end_time_parsed)

        if description is not None:
            update_fields.append("description = %s")
            update_values.append(description)

        if rrule is not None:
            update_fields.append("rrule = %s")
            update_values.append(rrule)

        if tags is not None:
            tags_json = utils.list_to_json(tags)
            update_fields.append("tags = %s")
            update_values.append(tags_json)

        if not update_fields:
            return current_event

        # Build and execute update query
        update_query = f"UPDATE calendar_entries SET {', '.join(update_fields)} WHERE id = %s"
        update_values.append(event_id)

        cursor.execute(update_query, update_values)
        database.get_connection().commit()

        # Get updated entry
        cursor.execute("SELECT * FROM calendar_entries WHERE id = %s", (event_id,))
        updated_event = cursor.fetchone()

        logger.info(f"Updated calendar entry with ID {event_id}")

        # Return the created event
        return {
            "id": updated_event["id"],
            "user_id": updated_event["user_id"],
            "title": updated_event["title"],
            "description": updated_event["description"],
            "start_datetime": updated_event["start_datetime"].isoformat(),
            "end_datetime": updated_event["end_datetime"].isoformat() if updated_event["end_datetime"] else None,
            "rrule": updated_event["rrule"],
            "tags": json.loads(updated_event["tags"]) if updated_event["tags"] else []
        }

    except Exception as e:
        database.get_connection().rollback()
        logger.error(f"Failed to update calendar entry: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update calendar entry: {str(e)}")

@router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Delete a calendar event"""
    # Validate user has access to this calendar entry
    requester_id = utils.validate_entry_access(api_key, utils.ResourceType.CALENDAR, event_id)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Check if the entry exists
        cursor.execute("SELECT * FROM calendar_entries WHERE id = %s", (event_id,))
        event = cursor.fetchone()

        if not event:
            logger.error(f"Calendar entry {event_id} not found for deletion")
            raise HTTPException(status_code=404, detail="Calendar entry not found")

        # Delete the entry
        delete_query = "DELETE FROM calendar_entries WHERE id = %s"
        cursor.execute(delete_query, (event_id,))

        # Commit the transaction
        database.get_connection().commit()

        logger.info(f"Deleted calendar entry with ID {event_id}")
        return {"message": f"Calendar entry with ID {event_id} deleted successfully"}
    except Exception as e:
        # Rollback in case of error
        database.get_connection().rollback()
        logger.error(f"Failed to delete calendar entry: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete calendar entry: {str(e)}")

@router.get("/search/", response_model=List[schemas.CalendarEvent])
async def search_events(
    query: str,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Search for events by title, description, or tags"""
    requester_id = utils.validate_user_for_action(api_key)

    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required.")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Split query into words for matching
        query_words = query.split()
        query_conds = ["user_id = %s"]
        query_params = [requester_id]

        # Add conditions for each word in the query
        for word in query_words:
            query_conds.append("(title LIKE %s OR description LIKE %s OR tags LIKE %s)")
            query_params.extend([f"%{word}%", f"%{word}%", f"%{word}%"])

        sql = "SELECT id, user_id, title, description, start_datetime, end_datetime, rrule, tags FROM calendar_entries WHERE " + " AND ".join(query_conds)
        cursor.execute(sql, tuple(query_params))
        
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        results = []
        for row in rows:
            item = {col: row[i] for i, col in enumerate(cols)}
            if isinstance(item.get("tags"), str):
                try:
                    item["tags"] = json.loads(item["tags"])
                except (json.JSONDecodeError, TypeError):
                    item["tags"] = []
            results.append(item)

        logger.info(f"Search found {len(results)} events for user {requester_id}")

        return results

    except Exception as e:
        logger.error(f"Failed to search calendar entries: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search calendar entries: {str(e)}")

@router.delete("/tags/{entry_id}")
async def delete_tag_from_event(
    entry_id: int,
    tag: str,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Delete a tag from a calendar event"""
    # Validate user has access to this calendar entry
    requester_id = utils.validate_entry_access(api_key, utils.ResourceType.CALENDAR, entry_id)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Check if the entry exists and get current tags
        cursor.execute("SELECT tags FROM calendar_entries WHERE id = %s", (entry_id,))
        result = cursor.fetchone()

        if not result:
            logger.error(f"Calendar entry {entry_id} not found for tag deletion")
            raise HTTPException(status_code=404, detail="Calendar entry not found")

        # Parse current tags
        current_tags_json = result[0]
        current_tags = []
        if current_tags_json:
            try:
                current_tags = json.loads(current_tags_json)
                if not isinstance(current_tags, list):
                    current_tags = [] # Ensure it's a list
            except (json.JSONDecodeError, TypeError):
                current_tags = []

        # Remove the specified tag if it exists
        if tag in current_tags:
            current_tags.remove(tag)
        else:
            logger.warning(f"Tag '{tag}' not found in calendar entry {entry_id}")
            raise HTTPException(status_code=404, detail=f"Tag '{tag}' not found in this calendar entry")

        # Convert back to JSON and update the database
        updated_tags_json = utils.list_to_json(current_tags) if current_tags else None
        update_query = "UPDATE calendar_entries SET tags = %s WHERE id = %s"
        cursor.execute(update_query, (updated_tags_json, entry_id))

        # Commit the transaction
        database.get_connection().commit()

        logger.info(f"Deleted tag '{tag}' from calendar entry with ID {entry_id}")
        return {"message": f"Tag '{tag}' deleted successfully from calendar entry with ID {entry_id}"}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        # Rollback in case of error
        database.get_connection().rollback()
        logger.error(f"Failed to delete tag for calendar entry: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete tag for calendar entry: {str(e)}")