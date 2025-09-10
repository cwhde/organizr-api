# Notes route of the API

import logging
from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional, List
import database
import utils
import schemas
import json

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=schemas.Note)
async def create_note(
    note: schemas.NoteCreate,
    for_user: Optional[str] = None,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Create a note with title, content, and optional tags."""
    target_user_id = utils.validate_user_for_action(api_key, for_user)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        tags_json = utils.list_to_json(note.tags) if note.tags else None

        insert_query = """
            INSERT INTO notes (user_id, title, content, tags)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(insert_query, (target_user_id, note.title, note.content, tags_json))
        note_id = cursor.lastrowid
        database.get_connection().commit()

        logger.info(f"Created note '{note.title}' for user {target_user_id} with ID {note_id}")

        # Fetch the created note to get all fields populated
        cursor.execute("SELECT id, user_id, title, content, tags, created_at, updated_at FROM notes WHERE id = %s", (note_id,))
        new_note_row = cursor.fetchone()
        cols = [d[0] for d in cursor.description]
        new_note = dict(zip(cols, new_note_row))
        new_note["tags"] = utils.json_to_list(new_note.get("tags"))

        return new_note

    except Exception as e:
        database.get_connection().rollback()
        logger.error(f"Failed to create note: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create note: {str(e)}")


def _build_get_notes_query(
    target_user_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[List[str]] = None,
    note_id: Optional[int] = None,
    match_mode: Optional[str] = "and",
):
    """Build SQL query and parameters for getting notes with filters"""
    base_query = "SELECT id, user_id, title, content, tags, created_at, updated_at FROM notes WHERE user_id = %s"
    query_params = [target_user_id]
    
    filter_conditions = []

    if note_id is not None:
        filter_conditions.append("id = %s")
        query_params.append(note_id)
    if title:
        filter_conditions.append("title LIKE %s")
        query_params.append(f"%{title}%")
    if content:
        filter_conditions.append("content LIKE %s")
        query_params.append(f"%{content}%")
    if tags:
        tag_conditions = []
        for tag in tags:
            tag_conditions.append("JSON_CONTAINS(tags, %s)")
            query_params.append(json.dumps(tag))
        
        if tag_conditions:
            tag_joiner = " AND " if match_mode.lower() == "and" else " OR "
            filter_conditions.append(f"({tag_joiner.join(tag_conditions)})")

    if filter_conditions:
        joiner = " AND " if match_mode.lower() == "and" else " OR "
        sql = f"{base_query} AND ({joiner.join(filter_conditions)})"
    else:
        sql = base_query
    
    return sql, tuple(query_params)


@router.get("/", response_model=List[schemas.Note])
async def get_notes(
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    note_id: Optional[int] = None,
    match_mode: Optional[str] = "and",
    for_user: Optional[str] = None,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """
    Get notes based on filters.
    - Pass no filters to get all notes for the user.
    - Filters can be combined in AND or OR mode.
    """
    target_user_id = utils.validate_user_for_action(api_key, for_user)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        sql, query_params = _build_get_notes_query(
            target_user_id, title, content, tags, note_id, match_mode
        )

        cursor.execute(sql, query_params)

        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        notes = [dict(zip(cols, row)) for row in rows]

        for note in notes:
            note["tags"] = utils.json_to_list(note.get("tags"))

        logger.info(f"Found {len(notes)} notes for user {target_user_id}")
        return notes

    except Exception as e:
        logger.error(f"Failed to get notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get notes: {str(e)}")


@router.put("/{note_id}", response_model=schemas.Note)
async def update_note(
    note_id: int,
    note_update: schemas.NoteUpdate,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Update a note's title, content, or tags."""
    utils.validate_entry_access(api_key, utils.ResourceType.NOTE, note_id)

    update_fields = []
    update_params = []

    if note_update.title is not None:
        update_fields.append("title = %s")
        update_params.append(note_update.title)
    if note_update.content is not None:
        update_fields.append("content = %s")
        update_params.append(note_update.content)
    if note_update.tags is not None:
        update_fields.append("tags = %s")
        update_params.append(utils.list_to_json(note_update.tags))

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_params.append(note_id)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        update_query = f"UPDATE notes SET {', '.join(update_fields)} WHERE id = %s"
        cursor.execute(update_query, tuple(update_params))
        database.get_connection().commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Note not found")

        # Fetch the updated note
        cursor.execute("SELECT id, user_id, title, content, tags, created_at, updated_at FROM notes WHERE id = %s", (note_id,))
        updated_note_row = cursor.fetchone()
        cols = [d[0] for d in cursor.description]
        updated_note = dict(zip(cols, updated_note_row))
        updated_note["tags"] = utils.json_to_list(updated_note.get("tags"))

        logger.info(f"Updated note {note_id}")
        return updated_note

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        database.get_connection().rollback()
        logger.error(f"Failed to update note {note_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update note {note_id}: {str(e)}")


@router.delete("/{note_id}", response_model=schemas.MessageResponse)
async def delete_note(
    note_id: int,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Delete a note by its ID."""
    utils.validate_entry_access(api_key, utils.ResourceType.NOTE, note_id)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        delete_query = "DELETE FROM notes WHERE id = %s"
        cursor.execute(delete_query, (note_id,))
        database.get_connection().commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Note not found")

        logger.info(f"Deleted note {note_id}")
        return {"message": "Note deleted successfully"}

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        database.get_connection().rollback()
        logger.error(f"Failed to delete note {note_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete note {note_id}: {str(e)}")