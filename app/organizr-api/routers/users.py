# User management routes

import logging
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List, Dict, Any
import database
import utils
import schemas

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=schemas.UserCreateResponse)
async def create_user(
    api_key: str = Header(..., alias="X-API-Key")
):
    """Create a new user (by admin only)"""
    user_id, user_role, _ = utils.validate_api_key(api_key)
    
    if not user_id or user_role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Generate new user credentials
        new_user_id = utils.generate_user_id()
        new_api_key = utils.generate_api_key()
        api_key_hash = utils.hash_api_key(new_api_key)
        
        # Insert new user
        cursor.execute(
            "INSERT INTO users (id, api_key_hash, role) VALUES (%s, %s, 'user')",
            (new_user_id, api_key_hash)
        )
        database.get_connection().commit()
        
        logger.info(f"New user created: {new_user_id}")
        
        return {
            "user_id": new_user_id,
            "api_key": new_api_key,
            "message": "User created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[schemas.User])
async def list_users(
    api_key: str = Header(..., alias="X-API-Key")
):
    """List all users (admin only)"""
    user_id, user_role, _ = utils.validate_api_key(api_key)
    
    if not user_id or user_role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")
        cursor.execute("SELECT id, role, created_at, updated_at FROM users")
        
        users = []
        for row in cursor.fetchall():
            users.append({
                "id": row[0],
                "role": row[1],
                "created_at": row[2].isoformat() if row[2] else None,
                "updated_at": row[3].isoformat() if row[3] else None
            })
        
        return users
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{user_id}", response_model=schemas.UserWithOffset)
async def get_user(
    user_id: str,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Get user details"""
    requester_id, _, has_permission = utils.validate_api_key(api_key, user_id)
    
    if not requester_id or not has_permission:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")
        cursor.execute(
            "SELECT id, role, utc_offset_minutes, created_at, updated_at FROM users WHERE id = %s",
            (user_id,)
        )
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": result[0],
            "role": result[1],
            "utc_offset_minutes": result[2],
            "created_at": result[3].isoformat() if result[3] else None,
            "updated_at": result[4].isoformat() if result[4] else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{user_id}", response_model=schemas.MessageResponse)
async def update_user(
    user_id: str,
    utc_offset_minutes: int,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Update user details"""
    requester_id, _, has_permission = utils.validate_api_key(api_key, user_id)
    
    if not requester_id or not has_permission:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")

        # Update user
        cursor.execute(
            "UPDATE users SET utc_offset_minutes = %s WHERE id = %s",
            (utc_offset_minutes, user_id)
        )
        database.get_connection().commit()
        
        return {"message": "User updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{user_id}", response_model=schemas.MessageResponse)
async def delete_user(
    user_id: str,
    api_key: str = Header(..., alias="X-API-Key")
):
    """Delete user (admin or self only)"""
    # Validate API key and permissions for target user
    requester_id, _, has_permission = utils.validate_api_key(api_key, user_id)
    if not requester_id or not has_permission:
        raise HTTPException(status_code=403, detail="Access denied")
 
    try:
        cursor = database.get_cursor()
        cursor.execute(f"USE {database.MYSQL_DATABASE}")
        # Prevent deletion of admin users
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        if result[0] == 'admin':
            raise HTTPException(status_code=403, detail="Admin users cannot be deleted")
         
         # Delete user (cascade will handle related data)
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        database.get_connection().commit()
        
        logger.info(f"User deleted: {user_id}")
        return {"message": "User deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
