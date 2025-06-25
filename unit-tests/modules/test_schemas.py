import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
from pydantic import ValidationError
from datetime import datetime
from schemas import *

def test_user(): 
    User(id="u1", role="admin")
    with pytest.raises(ValidationError): User(id=1)

def test_user_with_offset():
    UserWithOffset(id="u1", role="admin", utc_offset_minutes=120)
    with pytest.raises(ValidationError): UserWithOffset(id="u1", role="admin", utc_offset_minutes="x")

def test_user_create_response():
    UserCreateResponse(user_id="u1", api_key="k1", message="ok")
    with pytest.raises(ValidationError): UserCreateResponse(user_id="u1")

def test_calendar_event():
    CalendarEvent(id=1, user_id="u1", title="m", start_datetime=datetime.now(), end_datetime=datetime.now())
    with pytest.raises(ValidationError): CalendarEvent(id="x")

def test_calendar_event_create():
    CalendarEventCreate(id=1, user_id="u1", title="m", start_datetime="2023-01-01T10:00:00")
    with pytest.raises(ValidationError): CalendarEventCreate()

def test_message_response():
    MessageResponse(message="ok")
    with pytest.raises(ValidationError): MessageResponse(message=1)

def test_app():
    App(id=1, name="app", created_at=datetime.now())
    with pytest.raises(ValidationError): App(id=1, name=1)

def test_app_create():
    AppCreate(name="app")
    with pytest.raises(ValidationError): AppCreate()

def test_app_user_link():
    AppUserLink(id=1, app_id=1, user_id="u1", external_id="e1", created_at=datetime.now())
    with pytest.raises(ValidationError): AppUserLink(id=1, app_id="x")

def test_app_user_link_create():
    AppUserLinkCreate(user_id="u1", external_id="e1")
    with pytest.raises(ValidationError): AppUserLinkCreate(user_id="u1")

def test_translate_id_response():
    TranslateIdResponse(user_id="u1")
    with pytest.raises(ValidationError): TranslateIdResponse(user_id=1)