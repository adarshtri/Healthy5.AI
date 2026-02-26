from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal

class ChatMessage(BaseModel):
    user_id: int
    sender: Literal["user", "bot"]
    text: str
    context: Optional[str] = None
    message_id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class WeightEntry(BaseModel):
    user_id: int
    weight: float
    unit: str = "kg"
    date: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123456789,
                "weight": 75.5,
                "unit": "kg",
                "date": "2023-10-27T10:00:00"
            }
        }

class UserProfile(BaseModel):
    user_id: int
    name: Optional[str] = None
    age: Optional[int] = None
    bot_token: Optional[str] = None
    memories: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    active_agent: Literal["weight", "profile", "general", "remind"] = "general"
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123456789,
                "name": "Alice",
                "age": 30,
                "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                "memories": ["Lives in NYC", "Has a dog"],
                "preferences": ["Vegetarian", "Early riser"],
                "active_agent": "general"
            }
        }

class UserState(BaseModel):
    """Historical log of context switches"""
    user_id: int
    active_agent: Literal["weight", "profile", "general", "remind"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ReminderConfig(BaseModel):
    """Stores the recurring schedule settings."""
    user_id: int
    title: str
    action_type: Literal["message", "agent"] = "message"
    target_user_id: Optional[int] = None
    recurrence_type: Literal["daily", "interval"] = "daily"
    time_of_day: Optional[str] = None  # Format: "HH:MM" for daily
    days_of_week: list[int] = Field(default_factory=list)  # 0=Mon, 6=Sun. Empty=everyday
    interval_minutes: Optional[int] = None # For interval
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ReminderInstance(BaseModel):
    """A concrete occurrence of a reminder."""
    config_id: str  # Stringified ObjectId of ReminderConfig
    user_id: int
    title: str
    action_type: Literal["message", "agent"] = "message"
    target_user_id: Optional[int] = None
    scheduled_time: datetime
    status: Literal["pending", "notified", "completed", "skipped", "expired"] = "pending"
    telegram_message_id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
