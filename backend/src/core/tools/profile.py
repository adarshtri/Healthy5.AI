from typing import Annotated
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..database import get_db
from ..models import UserProfile

def get_user_id(config: RunnableConfig) -> int:
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        raise ValueError("User ID not found in context.")
    return int(user_id)

@tool
async def update_profile(
    name: Annotated[str | None, "The user's full name"] = None, 
    age: Annotated[int | None, "The user's age"] = None, 
    config: RunnableConfig = None
) -> str:
    """
    Updates the user's basic profile information (name, age).
    """
    try:
        user_id = get_user_id(config)
        db = await get_db()
        
        update_fields = {}
        if name:
            update_fields["name"] = name
        if age:
            update_fields["age"] = age
            
        if not update_fields:
            return "No profile changes provided."

        await db.profiles.update_one(
            {"user_id": user_id},
            {"$set": update_fields},
            upsert=True
        )
        
        changes = ", ".join(f"{k}: {v}" for k, v in update_fields.items())
        return f"✅ Profile updated successfully. Changes: {changes}"
    except Exception as e:
        return f"Error updating profile: {str(e)}"

@tool
async def add_memory(content: Annotated[str, "The fact or memory to save"], config: RunnableConfig) -> str:
    """
    Adds a long-term memory or fact about the user (e.g., "Lives in NYC", "Has a dog").
    """
    try:
        user_id = get_user_id(config)
        db = await get_db()
        
        await db.profiles.update_one(
            {"user_id": user_id},
            {"$addToSet": {"memories": content}}, # prevent duplicates
            upsert=True
        )
        return f"✅ Memory added: '{content}'"
    except Exception as e:
        return f"Error adding memory: {str(e)}"

@tool
async def add_preference(content: Annotated[str, "The user preference to save"], config: RunnableConfig) -> str:
    """
    Adds a user preference or short-term goal (e.g., "Likes vegetarian food", "Trying to sleep early").
    """
    try:
        user_id = get_user_id(config)
        db = await get_db()
        
        await db.profiles.update_one(
            {"user_id": user_id},
            {"$addToSet": {"preferences": content}},
            upsert=True
        )
        return f"✅ Preference added: '{content}'"
    except Exception as e:
        return f"Error adding preference: {str(e)}"

async def get_user_profile(user_id: int) -> dict:
    """
    Helper to fetch the full profile for context injection.
    Not a tool, but used by the graph.
    """
    db = await get_db()
    profile = await db.profiles.find_one({"user_id": user_id})
    if profile:
        return UserProfile(**profile).model_dump()
    return {}
