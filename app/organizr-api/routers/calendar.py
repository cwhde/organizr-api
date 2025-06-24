# Calendar CRUD routes

import logging
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List, Dict, Any
import database
import utils
import datetime
import schemas

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
    """Query calendar events of a user by text, tags, and/or time range"""
    if match_mode not in ["and", "or"]:
        raise HTTPException(status_code=400, detail="Invalid match_mode. Must be 'and' or 'or'.")

    target_user_id = utils.validate_user_for_action(api_key, for_user)

    if not any([search_text, tags, start_after, end_before]):
        raise HTTPException(status_code=400, detail="At least one search parameter (search_text, tags, start_after, end_before) must be provided.")

    time_range_specified = start_after is not None or end_before is not None

    start_date = utils.validate_time_format(start_after) if start_after else datetime.datetime.min
    end_date = utils.validate_time_format(end_before) if end_before else datetime.datetime.max

    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Invalid time format for start_after or end_before.")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        query_conditions = []
        query_params = []

        if search_text:
            text_condition = "(title LIKE %s OR description LIKE %s)"
            query_conditions.append(text_condition)
            query_params.extend([f"%{search_text}%", f"%{search_text}%"])

        if tags:
            tags_conditions = [f"JSON_CONTAINS(tags, '{{\"{tag}\": true}}')" for tag in tags]
            if match_mode == 'and':
                query_conditions.append(f"({' AND '.join(tags_conditions)})")
            else:
                query_conditions.append(f"({' OR '.join(tags_conditions)})")


        base_query = "SELECT * FROM calendar_entries WHERE user_id = %s"
        query_params.insert(0, target_user_id)

        # First, get all events matching the non-time-based criteria
        non_time_query = base_query
        if query_conditions:
            non_time_query += f" AND ({' ' + match_mode.upper() + ' ' .join(query_conditions)})"

        cursor.execute(non_time_query, query_params)
        all_matching_events = cursor.fetchall()

        # Separate events with and without rrule
        events_with_rrule = [event for event in all_matching_events if event['rrule']]
        events_without_rrule = [event for event in all_matching_events if not event['rrule']]

        final_results = []

        # Handle events without rrule
        for event in events_without_rrule:
            if start_date <= event['start_datetime'] <= end_date or start_date <= event['end_datetime'] <= end_date:
                final_results.append(event)

        # Handle events with rrule
        if time_range_specified:
            if match_mode == 'and':
                if events_with_rrule:
                     raise HTTPException(status_code=400, detail="Cannot query events with rrule in 'and' mode with a specific time range.")
            else: # OR mode
                # In OR mode, if a time range is specified, we cannot yet resolve rrules.
                utils.handle_rrule_query(events_with_rrule, start_date, end_date)
        else:
            # If no time range is specified, we can return all events with rrule that match other criteria
            final_results.extend(events_with_rrule)


        return final_results

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
