from .connection import get_db
from ..models import ChatMessage
from typing import List

async def get_chat_history(user_id: int, limit: int = 10) -> List[ChatMessage]:
    """
    Retrieves the last `limit` chat messages for a user, sorted by time ascending.
    """
    db = await get_db()
    cursor = db.chat_history.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    
    messages = []
    async for doc in cursor:
        messages.append(ChatMessage(**doc))
    
    # Reverse to return chronological order
    return messages[::-1]

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
