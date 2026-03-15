from .connection import get_db
from ..models import ChatMessage
from typing import List

async def get_chat_history(source_platform: str, source_id: str | int, limit: int = 10, skip: int = 0) -> List[ChatMessage]:
    """
    Retrieves the last `limit` chat messages for a user, sorted by time ascending.
    """
    db = await get_db()
    cursor = db.chat_history.find({
        "source_platform": source_platform, 
        "source_id": source_id
    }).sort("timestamp", -1).skip(skip).limit(limit)
    
    messages = []
    async for doc in cursor:
        messages.append(ChatMessage(**doc))
    
    # Reverse to return chronological order
    return messages[::-1]

async def save_chat_message(source_platform: str, source_id: str | int, sender: str, text: str):
    """
    Saves a message into the chat_history collection for agent context.
    """
    db = await get_db()
    message = ChatMessage(
        source_platform=source_platform,
        source_id=source_id,
        sender=sender,
        text=text
    )
    await db.chat_history.insert_one(message.model_dump())


async def get_user_state(user_id: int) -> str:
    """
    Retrieves the user's active agent state from their profile.
    Defaults to 'general' if not set.
    """
    db = await get_db()
    profile_doc = await db.profiles.find_one({"user_id": user_id})
    if profile_doc:
        return profile_doc.get("active_agent", "general")
    return "general"

async def set_user_state(user_id: int, agent_name: str):
    """
    Updates the user's active agent state on their profile and 
    appends a historical log entry in user_states.
    """
    db = await get_db()
    from datetime import datetime
    
    # 1. Update Profile's active state
    await db.profiles.update_one(
        {"user_id": user_id},
        {"$set": {"active_agent": agent_name}},
        upsert=True
    )
    
    # 2. Append to historical state log
    await db.user_states.insert_one({
        "user_id": user_id,
        "active_agent": agent_name,
        "timestamp": datetime.utcnow()
    })
