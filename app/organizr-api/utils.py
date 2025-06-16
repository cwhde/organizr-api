# Utility functions for the organizr api

import hashlib
import secrets
import string
import logging
import database

logger = logging.getLogger(__name__)

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
        if target_user_id is None:
            # No specific target, just validate the key
            has_permission = True
        elif user_role == 'admin':
            # Admin has permission over everyone
            has_permission = True
        elif user_id == target_user_id:
            # User has permission over their own data
            has_permission = True
        
        return user_id, user_role, has_permission
        
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        return None, None, False