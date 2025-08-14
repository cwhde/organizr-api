# Calendar CRUD routes

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
        database.commit()

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
        database.rollback()
        logger.error(f"Failed to create calendar entry: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create calendar entry: {str(e)}")

@router.get("/", response_model=List[schemas.CalendarEvent])
async def query_events(
        search_text: Optional[str] = None,
        tags: Optional[List[str]] = None,
        start_after: Optional[str] = None,
        end_before: Optional[str] = None,
        match_mode: Optional[str] = "and",
        for_user: Optional[str] = None,  # Let admin query events for other users
        api_key: str = Header(..., alias="X-API-Key"),
):
    """Query calendar events of a user by text, tags, and/or time range
    Parts:
    1) Non-recurring via SQL
    2) Recurring base rows via SQL when no time window
    3) Recurring occurrences via utils.handle_rrule_query when a time window is provided
    """

    # Validate user has access to this calendar
    requester_id = utils.validate_user_for_action(api_key, for_user)

    if not any([search_text, tags, start_after, end_before]):
        raise HTTPException(status_code=400, detail="At least one query filter must be provided.")

    # Normalize time window; defaults to min/max to avoid errors
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

    def build_text_tags_filters() -> (List[str], List[Any]):
        conds: List[str] = []
        params: List[Any] = []
        if search_text:
            conds.append("(title LIKE %s OR description LIKE %s)")
            like = f"%{search_text}%"
            params.extend([like, like])
        if tags:
            mode = (match_mode or "and").lower()
            if mode not in ("and", "or"):
                raise HTTPException(status_code=400, detail="Invalid match_mode. Use 'and' or 'or'.")
            tag_conds = []
            for tag in tags:
                tag_conds.append("JSON_CONTAINS(tags, %s)")
                params.append(f'"{tag}"')
            if tag_conds:
                if mode == "and":
                    conds.append(f"({' AND '.join(tag_conds)})")
                else:
                    conds.append(f"({' OR '.join(tag_conds)})")
        return conds, params

    def row_to_dict(columns: List[str], row: tuple) -> Dict[str, Any]:
        item = {col: row[i] for i, col in enumerate(columns)}
        # Normalize JSON fields
        raw_tags = item.get("tags")
        if isinstance(raw_tags, str):
            try:
                item["tags"] = json.loads(raw_tags)
            except Exception:
                item["tags"] = None
        # Ensure datetime fields exist
        return item

    def post_filter(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        mode = (match_mode or "and").lower()
        def match_item(it: Dict[str, Any]) -> bool:
            if search_text:
                title = (it.get("title") or "")
                desc = (it.get("description") or "")
                if (search_text.lower() not in title.lower()) and (search_text.lower() not in desc.lower()):
                    return False
            if tags:
                ev_tags = it.get("tags") or []
                if not isinstance(ev_tags, list):
                    try:
                        ev_tags = json.loads(ev_tags) if ev_tags else []
                    except Exception:
                        ev_tags = []
                if mode == "and":
                    if not all(t in ev_tags for t in tags):
                        return False
                else:
                    if not any(t in ev_tags for t in tags):
                        return False
            return True
        return [it for it in items if match_item(it)]

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Common text/tags filters
        tt_conds, tt_params = build_text_tags_filters()

        results: List[Dict[str, Any]] = []

        # Part 1: Non-recurring events via SQL (overlap with window)
        base_conds = ["user_id = %s", "(rrule IS NULL OR rrule = '')",
                      "start_datetime <= %s AND COALESCE(end_datetime, start_datetime) >= %s"]
        base_params: List[Any] = [requester_id, end_dt, start_dt]
        if tt_conds:
            base_conds.extend(tt_conds)
            base_params.extend(tt_params)
        sql_non_rrule = f"SELECT id, user_id, title, description, start_datetime, end_datetime, rrule, tags FROM calendar_entries WHERE {' AND '.join(base_conds)}"
        cursor.execute(sql_non_rrule, tuple(base_params))
        cols_non = [d[0] for d in cursor.description]
        rows_non = cursor.fetchall()
        non_rrule_items = [row_to_dict(cols_non, r) for r in rows_non]
        results.extend(non_rrule_items)

        # Recurring handling
        if has_time_window:
            # Part 3: Expand recurring occurrences within [start_dt, end_dt)
            recur_conds = ["user_id = %s", "(rrule IS NOT NULL AND rrule <> '')", "start_datetime <= %s"]
            recur_params: List[Any] = [requester_id, end_dt]
            if tt_conds:
                recur_conds.extend(tt_conds)
                recur_params.extend(tt_params)
            sql_recur = f"SELECT id, user_id, title, description, start_datetime, end_datetime, rrule, tags FROM calendar_entries WHERE {' AND '.join(recur_conds)}"
            cursor.execute(sql_recur, tuple(recur_params))
            cols_rec = [d[0] for d in cursor.description]
            rows_rec = cursor.fetchall()
            # Convert DB rows to dicts with proper types for utils
            recur_events: List[Dict[str, Any]] = []
            for r in rows_rec:
                ev = row_to_dict(cols_rec, r)
                # Ensure tags is a list (not JSON string)
                if isinstance(ev.get("tags"), str):
                    try:
                        ev["tags"] = json.loads(ev["tags"]) if ev["tags"] else None
                    except Exception:
                        ev["tags"] = None
                recur_events.append(ev)
            # Expand occurrences
            occurrences = utils.handle_rrule_query(recur_events, start_dt, end_dt)
            # Post-filter for text/tags to be safe
            occurrences = post_filter(occurrences)
            results.extend(occurrences)
        else:
            # Part 2: No time window -> return base recurring rows via SQL (like part 1 conditions but across all time)
            recur_conds = ["user_id = %s", "(rrule IS NOT NULL AND rrule <> '')"]
            recur_params: List[Any] = [requester_id]
            if tt_conds:
                recur_conds.extend(tt_conds)
                recur_params.extend(tt_params)
            sql_recur_base = f"SELECT id, user_id, title, description, start_datetime, end_datetime, rrule, tags FROM calendar_entries WHERE {' AND '.join(recur_conds)}"
            cursor.execute(sql_recur_base, tuple(recur_params))
            cols_rec_base = [d[0] for d in cursor.description]
            rows_rec_base = cursor.fetchall()
            recur_base_items = [row_to_dict(cols_rec_base, r) for r in rows_rec_base]
            results.extend(recur_base_items)

        # Sort combined results for readability
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

        cursor.execute("SELECT * FROM calendar_entries WHERE id = %s", (entry_id,))
        event = cursor.fetchone()

        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        return event

    except Exception as e:
        logger.error(f"Failed to retrieve calendar entry {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve calendar entry {entry_id}: {str(e)}")


@router.put("/{entry_id}", response_model=schemas.CalendarEvent)
async def update_event(
    entry_id: int,
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
    requester_id = utils.validate_entry_access(api_key, utils.ResourceType.CALENDAR, entry_id)

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
        cursor.execute("SELECT * FROM calendar_entries WHERE id = %s", (entry_id,))
        current_event = cursor.fetchone()

        if not current_event:
            logger.error(f"Calendar entry {entry_id} not found")
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
        update_values.append(entry_id)

        cursor.execute(update_query, update_values)
        database.get_connection().commit()

        # Get updated entry
        cursor.execute("SELECT * FROM calendar_entries WHERE id = %s", (entry_id,))
        updated_event = cursor.fetchone()

        logger.info(f"Updated calendar entry {entry_id} for user {requester_id}")
        return updated_event

    except Exception as e:
        database.get_connection().rollback()
        logger.error(f"Failed to update calendar entry {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update calendar entry: {str(e)}")

@router.delete("/{entry_id}", response_model=schemas.MessageResponse)
async def delete_event(
    entry_id: int,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Delete a calendar event"""
    # Validate user has access to this calendar entry
    requester_id = utils.validate_entry_access(api_key, utils.ResourceType.CALENDAR, entry_id)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Check if the entry exists
        cursor.execute("SELECT * FROM calendar_entries WHERE id = %s", (entry_id,))
        event = cursor.fetchone()

        if not event:
            logger.error(f"Calendar entry {entry_id} not found for deletion")
            raise HTTPException(status_code=404, detail="Calendar entry not found")

        # Delete the entry
        cursor.execute("DELETE FROM calendar_entries WHERE id = %s", (entry_id,))
        database.get_connection().commit()

        logger.info(f"Deleted calendar entry {entry_id} for user {requester_id}")
        return {"message": "Calendar entry deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        database.get_connection().rollback()
        logger.error(f"Failed to delete calendar entry {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete calendar entry: {str(e)}")
