from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ReceivedMessage(BaseModel):
    """
    Normalized event representing an incoming message or trigger
    from ANY source (Telegram, WhatsApp, Cron, Admin).
    """
    source_platform: str = Field(..., description="E.g., 'telegram', 'whatsapp', 'cron', 'admin'")
    source_id: str = Field(..., description="The ID of the user on the specific platform (like Telegram Chat ID)")
    internal_user_id: Optional[str] = Field(None, description="The internal DB ID of the user, if known")
    bot_token_or_id: str = Field(..., description="The specific Bot Token or ID that received this event")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Payload specific to the platform, normalized or raw
    text_content: Optional[str] = Field(None, description="The text of the message, if applicable")
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="The original raw payload for fallback")

class DeliverMessage(BaseModel):
    """
    Event representing a finalized response that needs to be sent out
    to a specific platform.
    """
    target_platform: str = Field(..., description="E.g., 'telegram', 'whatsapp'")
    target_id: str = Field(..., description="The ID of the user to send the message to (e.g. Chat ID)")
    bot_token_or_id: str = Field(..., description="The specific Bot Token or ID to use for dispatching")
    text_content: str = Field(..., description="The compiled text of the response")
    
    # Optional metadata like images, buttons, etc. can be added later
    media_url: Optional[str] = None
    reply_to_message_id: Optional[str] = None
