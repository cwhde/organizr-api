"""
Tests for app/app.py module
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add app and root directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))

from app import app

client = TestClient(app)

class TestApp:
    """Tests for the main FastAPI application"""

    def test_health_check(self):
        """Test the /health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_routers_included(self):
        """Test that all routers are included in the app"""
        # Get all routes from the app
        app_routes = [route.path for route in app.routes]

        # Check if routes from users, calendar, and apps routers are present
        assert "/users/" in app_routes
        assert "/calendar/" in app_routes
        assert "/apps/" in app_routes
