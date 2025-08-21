# Tasks CRUD routes

import logging
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List, Dict, Any, Tuple
import database
import utils
import datetime
import schemas
import json

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=schemas.TaskCreate)
async def create_task(
    title: str,
    description: Optional[str] = None,
    status: Optional[schemas.TaskStatus] = schemas.TaskStatus.PENDING,
    due_date: Optional[str] = None,
    rrule: Optional[str] = None,
    tags: Optional[List[str]] = None,
    for_user: Optional[str] = None,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Create a new task"""
    target_user_id = utils.validate_user_for_action(api_key, for_user)

    # Validate due_date format if provided
    due_date_parsed = None
    if due_date:
        try:
            due_date_parsed = utils.validate_time_format(due_date)
            if due_date_parsed is None:
                raise ValueError("Invalid date format")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid due_date format: {e}")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Convert tags list to JSON
        tags_json = utils.list_to_json(tags) if tags else None

        # Insert task into database
        insert_query = """
            INSERT INTO tasks 
            (user_id, title, description, status, due_date, rrule, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(insert_query, (
            target_user_id,
            title,
            description,
            status.value,
            due_date_parsed,
            rrule,
            tags_json
        ))

        # Get the newly created task ID
        task_id = cursor.lastrowid
        database.get_connection().commit()

        logger.info(f"Created task '{title}' for user {target_user_id} with ID {task_id}")

        # Return the created task
        return {
            "user_id": target_user_id,
            "title": title,
            "description": description,
            "status": status,
            "due_date": due_date,
            "rrule": rrule,
            "tags": tags
        }

    except Exception as e:
        database.get_connection().rollback()
        logger.error(f"Failed to create task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

@router.get("/", response_model=List[schemas.Task])
async def query_tasks(
    search_text: Optional[str] = None,
    tags: Optional[List[str]] = None,
    due_after: Optional[str] = None,
    due_before: Optional[str] = None,
    status: Optional[schemas.TaskStatus] = None,
    match_mode: Optional[str] = "and",
    for_user: Optional[str] = None,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Query tasks with optional text, tags, status, and/or due date window.
    Logic mirrors calendar querying:
    1) Non-recurring via SQL
    2) Recurring base rows via SQL when no time window
    3) Recurring occurrences via utils.handle_rrule_query when a time window is provided
    """

    # Validate user context
    requester_id = utils.validate_user_for_action(api_key, for_user)

    if not any([search_text, tags, due_after, due_before, status]):
        raise HTTPException(status_code=400, detail="At least one query filter must be provided.")

    # Parse time window
    start_dt = datetime.datetime.min
    end_dt = datetime.datetime.max
    if due_after:
        start_dt = utils.validate_time_format(due_after)
        if start_dt is None:
            raise HTTPException(status_code=400, detail="Invalid 'due_after' time format")
    if due_before:
        end_dt = utils.validate_time_format(due_before)
        if end_dt is None:
            raise HTTPException(status_code=400, detail="Invalid 'due_before' time format")

    has_time_window = bool(due_after or due_before)

    def build_text_tags_filters() -> Tuple[List[str], List[Any]]:
        conds: List[str] = []
        params: List[Any] = []
        if search_text:
            conds.append("(title LIKE %s OR description LIKE %s)")
            like = f"%{search_text}%"
            params.extend([like, like])
        if status is not None:
            conds.append("status = %s")
            params.append(status.value)
        if tags:
            mode = (match_mode or "and").lower()
            if mode not in ("and", "or"):
                raise HTTPException(status_code=400, detail="match_mode must be 'and' or 'or'")
            tag_conds = []
            for t in tags:
                # Check JSON array contains the tag
                tag_conds.append("JSON_CONTAINS(tags, JSON_QUOTE(%s), '$')")
                params.append(t)
            joiner = " AND " if mode == "and" else " OR "
            conds.append(f"({joiner.join(tag_conds)})")
        return conds, params

    def row_to_task_dict(columns: List[str], row: tuple) -> Dict[str, Any]:
        item = {col: row[i] for i, col in enumerate(columns)}
        # Normalize tags JSON
        raw_tags = item.get("tags")
        if isinstance(raw_tags, str):
            try:
                item["tags"] = json.loads(raw_tags)
            except (json.JSONDecodeError, TypeError):
                item["tags"] = []
        return item

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        tt_conds, tt_params = build_text_tags_filters()

        results: List[Dict[str, Any]] = []

        # Part 1: Non-recurring (no rrule) via SQL
        base_conds = [
            "user_id = %s",
            "(rrule IS NULL OR rrule = '')",
        ]
        base_params: List[Any] = [requester_id]
        if has_time_window:
            base_conds.append("due_date IS NOT NULL AND due_date <= %s AND due_date >= %s")
            base_params.extend([end_dt, start_dt])
        if tt_conds:
            base_conds.extend(tt_conds)
            base_params.extend(tt_params)
        sql_non_rrule = (
            "SELECT id, user_id, title, description, status, due_date, rrule, tags "
            "FROM tasks WHERE " + " AND ".join(base_conds)
        )
        cursor.execute(sql_non_rrule, tuple(base_params))
        cols_non = [d[0] for d in cursor.description]
        rows_non = cursor.fetchall()
        non_rrule_items = [row_to_task_dict(cols_non, r) for r in rows_non]
        results.extend(non_rrule_items)

        # Part 2/3: Recurring handling
        if has_time_window:
            # Fetch recurring base rows filtered by text/status/tags (but not time)
            rec_conds = [
                "user_id = %s",
                "(rrule IS NOT NULL AND rrule <> '')",
            ]
            rec_params: List[Any] = [requester_id]
            if tt_conds:
                rec_conds.extend(tt_conds)
                rec_params.extend(tt_params)
            sql_rrule = (
                "SELECT id, user_id, title, description, status, due_date, rrule, tags "
                "FROM tasks WHERE " + " AND ".join(rec_conds)
            )
            cursor.execute(sql_rrule, tuple(rec_params))
            cols_r = [d[0] for d in cursor.description]
            rows_r = cursor.fetchall()
            rrule_rows = [row_to_task_dict(cols_r, r) for r in rows_r]

            # Map tasks to events shape for RRULE expansion (due_date as start/end)
            events = []
            id_to_status: Dict[int, Any] = {}
            for it in rrule_rows:
                if it.get("id") is not None:
                    id_to_status[int(it.get("id"))] = it.get("status")
                events.append({
                    "id": it.get("id"),
                    "user_id": it.get("user_id"),
                    "title": it.get("title"),
                    "description": it.get("description"),
                    "start_datetime": it.get("due_date"),
                    "end_datetime": it.get("due_date"),
                    "rrule": it.get("rrule"),
                    "tags": it.get("tags") or [],
                })

            occurrences = utils.handle_rrule_query(events, start_dt, end_dt)

            # Convert occurrences back to task-like dicts
            for occ in occurrences:
                occ_id = occ.get("id")
                occ_status = id_to_status.get(int(occ_id)) if occ_id is not None else None
                if not occ_status:
                    occ_status = schemas.TaskStatus.PENDING.value
                results.append({
                    "id": occ.get("id"),
                    "user_id": occ.get("user_id"),
                    "title": occ.get("title"),
                    "description": occ.get("description"),
                    "status": occ_status,
                    "due_date": occ.get("start_datetime"),
                    "rrule": occ.get("rrule"),
                    "tags": occ.get("tags") or [],
                })
        else:
            # No time window: return base rows of recurring tasks via SQL
            rec_base_conds = [
                "user_id = %s",
                "(rrule IS NOT NULL AND rrule <> '')",
            ]
            rec_base_params: List[Any] = [requester_id]
            if tt_conds:
                rec_base_conds.extend(tt_conds)
                rec_base_params.extend(tt_params)
            sql_rrule_base = (
                "SELECT id, user_id, title, description, status, due_date, rrule, tags "
                "FROM tasks WHERE " + " AND ".join(rec_base_conds)
            )
            cursor.execute(sql_rrule_base, tuple(rec_base_params))
            cols_b = [d[0] for d in cursor.description]
            rows_b = cursor.fetchall()
            results.extend([row_to_task_dict(cols_b, r) for r in rows_b])

        # Sort results by due_date then id
        results.sort(key=lambda x: (x.get("due_date") or datetime.datetime.min, x.get("id") or 0))

        logger.info(f"Found {len(results)} tasks for user {requester_id}")

        # Ensure each task has a status (default to pending if missing)
        for it in results:
            if not it.get("status"):
                it["status"] = schemas.TaskStatus.PENDING.value

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to query tasks: {str(e)}")


@router.get("/{entry_id}", response_model=schemas.Task)
async def get_task(
    entry_id: int,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Get a single task by query id"""
    utils.validate_entry_access(api_key, utils.ResourceType.TASK, entry_id)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        cursor.execute("SELECT * FROM tasks WHERE id = %s", (entry_id,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Task not found")

        # Get column names
        columns = [desc[0] for desc in cursor.description]
        task_dict = dict(zip(columns, result))

        # Parse JSON tags field
        if task_dict.get("tags"):
            try:
                task_dict["tags"] = json.loads(task_dict["tags"])
            except (json.JSONDecodeError, TypeError):
                task_dict["tags"] = []

        logger.info(f"Retrieved task {entry_id}")
        return task_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve task {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve task {entry_id}: {str(e)}")

@router.put("/{entry_id}", response_model=schemas.Task)
async def update_task(
    entry_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[schemas.TaskStatus] = None,
    due_date: Optional[str] = None,
    rrule: Optional[str] = None,
    tags: Optional[List[str]] = None,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Update an existing task"""
    utils.validate_entry_access(api_key, utils.ResourceType.TASK, entry_id)

    # Validate due_date format if provided
    due_date_parsed = None
    if due_date is not None:
        try:
            due_date_parsed = utils.validate_time_format(due_date)
            if due_date_parsed is None:
                raise ValueError("Invalid date format")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid due_date format: {e}")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # First check if task exists
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (entry_id,))
        current_task = cursor.fetchone()

        if not current_task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Prepare update values
        update_fields = []
        update_values = []

        if title is not None:
            update_fields.append("title = %s")
            update_values.append(title)

        if description is not None:
            update_fields.append("description = %s")
            update_values.append(description)

        if status is not None:
            update_fields.append("status = %s")
            update_values.append(status.value)

        if due_date is not None:
            update_fields.append("due_date = %s")
            update_values.append(due_date_parsed)

        if rrule is not None:
            update_fields.append("rrule = %s")
            update_values.append(rrule)

        if tags is not None:
            update_fields.append("tags = %s")
            update_values.append(utils.list_to_json(tags))

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update provided")

        # Build and execute update query
        update_query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = %s"
        update_values.append(entry_id)

        cursor.execute(update_query, update_values)
        database.get_connection().commit()

        # Get updated task
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (entry_id,))
        result = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        task_dict = dict(zip(columns, result))

        # Parse JSON tags field
        if task_dict.get("tags"):
            try:
                task_dict["tags"] = json.loads(task_dict["tags"])
            except (json.JSONDecodeError, TypeError):
                task_dict["tags"] = []

        logger.info(f"Updated task {entry_id}")
        return task_dict

    except HTTPException:
        raise
    except Exception as e:
        database.get_connection().rollback()
        logger.error(f"Failed to update task {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update task {entry_id}: {str(e)}")

@router.delete("/{entry_id}", response_model=schemas.MessageResponse)
async def delete_task(
    entry_id: int,
    api_key: str = Header(..., alias="X-API-Key"),
):
    """Delete a task"""
    utils.validate_entry_access(api_key, utils.ResourceType.TASK, entry_id)

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Check if task exists
        cursor.execute("SELECT id FROM tasks WHERE id = %s", (entry_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Task not found")

        # Delete the task
        cursor.execute("DELETE FROM tasks WHERE id = %s", (entry_id,))
        database.get_connection().commit()

        logger.info(f"Deleted task {entry_id}")
        return {"message": f"Task {entry_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        database.get_connection().rollback()
        logger.error(f"Failed to delete task {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete task {entry_id}: {str(e)}")