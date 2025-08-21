from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


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

class Task(BaseModel):
    id: int
    user_id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    due_date: Optional[datetime] = None
    rrule: Optional[str] = None
    tags: Optional[List[str]] = []


class TaskCreate(BaseModel):
    user_id: str
    title: str
    description: Optional[str] = None
    status: Optional[TaskStatus] = TaskStatus.PENDING
    due_date: Optional[str] = None
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


class Note(BaseModel):
    id: int
    user_id: str
    title: str
    content: str
    tags: Optional[List[str]] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NoteCreate(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = []


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = []
