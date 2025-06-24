from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class User(BaseModel):
    id: str
    role: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserWithOffset(User):
    utc_offset_minutes: Optional[int] = None


class UserCreateResponse(BaseModel):
    user_id: str
    api_key: str
    message: str


class CalendarEvent(BaseModel):
    id: int
    user_id: str
    title: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    rrule: Optional[str] = None
    tags: Optional[List[str]] = []


class CalendarEventCreate(BaseModel):
    id: int
    user_id: str
    title: str
    description: Optional[str] = None
    start_datetime: str
    end_datetime: Optional[str] = None
    rrule: Optional[str] = None
    tags: Optional[List[str]] = []


class MessageResponse(BaseModel):
    message: str


class App(BaseModel):
    id: int
    name: str
    created_at: datetime


class AppCreate(BaseModel):
    name: str


class AppUserLink(BaseModel):
    id: int
    app_id: int
    user_id: str
    external_id: str
    created_at: datetime


class AppUserLinkCreate(BaseModel):
    user_id: str
    external_id: str


class TranslateIdResponse(BaseModel):
    user_id: Optional[str] = None
    external_id: Optional[str] = None
