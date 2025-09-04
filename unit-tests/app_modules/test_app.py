# Test the main app file of the API

import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
from fastapi.testclient import TestClient
from unittest.mock import patch
import app

@pytest.fixture(scope="module", autouse=True)
def setup_module():
    """Setup the database for the module."""
    import unit_test_utils
    unit_test_utils.clean_tables()

def test_app_initialization():
    # Test app is created with correct config
    assert app.app.title == "Organizr-API"

def test_routers_included():
    # Test all routers are included with correct prefixes
    routes = [route.path for route in app.app.routes]
    assert "/users" in str(routes)
    assert "/calendar" in str(routes) 
    assert "/apps" in str(routes)

def test_health_endpoint():
    client = TestClient(app.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch('app.setup.setup_database')
def test_database_setup_called(mock_setup):
    # Test that setup_database is called during app initialization
    # This verifies the startup behavior without re-importing
    import importlib
    importlib.reload(app)
    mock_setup.assert_called_once()

def test_app_startup_error_handling():
    # Test app handles database connection issues gracefully
    with patch('app.database.get_connection', side_effect=Exception("DB Error")):
        with pytest.raises(Exception, match="DB Error"):
            import importlib
            importlib.reload(app)