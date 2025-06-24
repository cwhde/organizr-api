# App management routes

import logging
from fastapi import APIRouter, HTTPException, Header, Query
from typing import List, Optional
import database
import utils
import schemas

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=schemas.App)
async def create_app(
    app_create: schemas.AppCreate,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Register a new client application"""
    user_id, user_role, _ = utils.validate_api_key(api_key)

    if not user_id or user_role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        cursor.execute(
            "INSERT INTO apps (name) VALUES (%s)",
            (app_create.name,)
        )
        database.get_connection().commit()

        cursor.execute("SELECT id, name, created_at FROM apps WHERE name = %s", (app_create.name,))
        new_app = cursor.fetchone()

        return {"id": new_app[0], "name": new_app[1], "created_at": new_app[2]}

    except Exception as e:
        logger.error(f"Error creating app: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[schemas.App])
async def list_apps(
    api_key: str = Header(..., alias="X-API-Key")
):
    """Retrieve a list of all registered client applications"""
    user_id, user_role, _ = utils.validate_api_key(api_key)

    if not user_id or user_role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")
        cursor.execute("SELECT id, name, created_at FROM apps")

        apps = []
        for row in cursor.fetchall():
            apps.append({"id": row[0], "name": row[1], "created_at": row[2]})

        return apps

    except Exception as e:
        logger.error(f"Error listing apps: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{app_name}", response_model=schemas.App)
async def update_app(
    app_name: str,
    app_update: schemas.AppCreate,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Update the name of an existing application"""
    user_id, user_role, _ = utils.validate_api_key(api_key)

    if not user_id or user_role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        cursor.execute("UPDATE apps SET name = %s WHERE name = %s", (app_update.name, app_name))
        database.get_connection().commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="App not found")

        cursor.execute("SELECT id, name, created_at FROM apps WHERE name = %s", (app_update.name,))
        updated_app = cursor.fetchone()

        return {"id": updated_app[0], "name": updated_app[1], "created_at": updated_app[2]}

    except Exception as e:
        logger.error(f"Error updating app: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{app_name}", response_model=schemas.MessageResponse)
async def delete_app(
    app_name: str,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Delete an application and all of its associated user links"""
    user_id, user_role, _ = utils.validate_api_key(api_key)

    if not user_id or user_role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        cursor.execute("DELETE FROM apps WHERE name = %s", (app_name,))
        database.get_connection().commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="App not found")

        return {"message": "App deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting app: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{app_name}/users", response_model=schemas.AppUserLink)
async def create_user_link(
    app_name: str,
    link_create: schemas.AppUserLinkCreate,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Create a link between an existing internal user ID and an external user ID"""
    user_id, user_role, _ = utils.validate_api_key(api_key)

    if not user_id or user_role != 'admin':
        logger.warning(f"Non-admin user {user_id} attempted to create app user link")
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Check if app exists
        cursor.execute("SELECT id FROM apps WHERE name = %s", (app_name,))
        app = cursor.fetchone()
        if not app:
            logger.error(f"App {app_name} not found when creating user link")
            raise HTTPException(status_code=404, detail="App not found")
        app_id = app[0]

        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE id = %s", (link_create.user_id,))
        user = cursor.fetchone()
        if not user:
            logger.error(f"User {link_create.user_id} not found when creating app user link")
            raise HTTPException(status_code=404, detail=f"User with ID {link_create.user_id} not found")

        try:
            cursor.execute(
                "INSERT INTO app_user_links (app_id, user_id, external_id) VALUES (%s, %s, %s)",
                (app_id, link_create.user_id, link_create.external_id)
            )
            database.get_connection().commit()
        except Exception as e:
            if "Duplicate entry" in str(e):
                logger.warning(f"Attempted to create duplicate app user link: {str(e)}")
                raise HTTPException(status_code=409, detail="A link for this app and user or external ID already exists")
            else:
                raise

        cursor.execute(
            "SELECT id, app_id, user_id, external_id, created_at FROM app_user_links WHERE app_id = %s AND user_id = %s",
            (app_id, link_create.user_id)
        )
        new_link = cursor.fetchone()

        logger.info(f"Created user link for app {app_name} (ID: {app_id}) and user {link_create.user_id}")
        return {"id": new_link[0], "app_id": new_link[1], "user_id": new_link[2], "external_id": new_link[3], "created_at": new_link[4]}

    except HTTPException:
        raise
    except Exception as e:
        database.get_connection().rollback()
        logger.error(f"Error creating user link: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user link: {str(e)}")

@router.get("/{app_name}/users", response_model=List[schemas.AppUserLink])
async def list_user_links(
    app_name: str,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Retrieve a list of all user links for a specific application"""
    user_id, user_role, _ = utils.validate_api_key(api_key)

    if not user_id or user_role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        cursor.execute("SELECT id FROM apps WHERE name = %s", (app_name,))
        app = cursor.fetchone()
        if not app:
            raise HTTPException(status_code=404, detail="App not found")
        app_id = app[0]

        cursor.execute(
            "SELECT id, app_id, user_id, external_id, created_at FROM app_user_links WHERE app_id = %s",
            (app_id,)
        )

        links = []
        for row in cursor.fetchall():
            links.append({"id": row[0], "app_id": row[1], "user_id": row[2], "external_id": row[3], "created_at": row[4]})

        return links

    except Exception as e:
        logger.error(f"Error listing user links: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{app_name}/users/{external_id}", response_model=schemas.MessageResponse)
async def delete_user_link(
    app_name: str,
    external_id: str,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Delete a specific user link"""
    user_id, user_role, _ = utils.validate_api_key(api_key)

    if not user_id or user_role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        cursor.execute("SELECT id FROM apps WHERE name = %s", (app_name,))
        app = cursor.fetchone()
        if not app:
            raise HTTPException(status_code=404, detail="App not found")
        app_id = app[0]

        cursor.execute(
            "DELETE FROM app_user_links WHERE app_id = %s AND external_id = %s",
            (app_id, external_id)
        )
        database.get_connection().commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User link not found")

        return {"message": "User link deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting user link: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{app_name}/translate", response_model=schemas.TranslateIdResponse)
async def translate_id(
    app_name: str,
    external_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    api_key: str = Header(..., alias="X-API-Key")
):
    """Translate an ID between the external and internal domains"""
    requester_id, user_role, _ = utils.validate_api_key(api_key)

    if not requester_id or user_role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    if not external_id and not user_id:
        raise HTTPException(status_code=400, detail="Either external_id or user_id must be provided")

    if external_id and user_id:
        raise HTTPException(status_code=400, detail="Provide either external_id or user_id, not both")

    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        cursor.execute("SELECT id FROM apps WHERE name = %s", (app_name,))
        app = cursor.fetchone()
        if not app:
            raise HTTPException(status_code=404, detail="App not found")
        app_id = app[0]

        if external_id:
            cursor.execute(
                "SELECT user_id FROM app_user_links WHERE app_id = %s AND external_id = %s",
                (app_id, external_id)
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            return {"user_id": result[0]}

        else: # user_id is provided
            cursor.execute(
                "SELECT external_id FROM app_user_links WHERE app_id = %s AND user_id = %s",
                (app_id, user_id)
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            return {"external_id": result[0]}

    except Exception as e:
        logger.error(f"Error translating ID: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
