from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from datetime import datetime, timedelta
from ..database import get_db
from ..models import WeightEntry

def get_user_id(config: RunnableConfig) -> int:
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        raise ValueError("User ID not found in context.")
    return int(user_id)

def parse_date(date_str: str) -> datetime:
    """Parses date string YYYY-MM-DD to datetime object at start of day."""
    if not date_str:
        return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")

async def _log_weight_logic(weight: float, date: str = None, config: RunnableConfig = None) -> str:
    """Helper logic for logging/updating weight."""
    try:
        user_id = get_user_id(config)
        date_obj = parse_date(date)
        
        db = await get_db()
        
        result = await db.weights.update_one(
            {"user_id": user_id, "date": date_obj},
            {"$set": {"weight": weight, "unit": "kg"}},
            upsert=True
        )
        
        date_display = date_obj.strftime("%Y-%m-%d")
        if result.upserted_id:
            return f"✅ Weight logged: {weight} kg for {date_display}"
        else:
            return f"✅ Weight updated: {weight} kg for {date_display}"
            
    except Exception as e:
        return f"Error logging weight: {str(e)}"

@tool
async def log_weight(weight: float, date: str = None, config: RunnableConfig = None) -> str:
    """
    Logs a weight entry. If a date is provided (YYYY-MM-DD), logs for that date.
    Default is today. Overwrites if an entry exists for that date.
    """
    return await _log_weight_logic(weight, date, config)

@tool
async def update_weight(weight: float, date: str = None, config: RunnableConfig = None) -> str:
    """
    Updates a weight entry for a specific date (YYYY-MM-DD). Default is today.
    """
    return await _log_weight_logic(weight, date, config)

@tool
async def delete_weight(date: str = None, config: RunnableConfig = None) -> str:
    """
    Deletes a weight entry for a specific date (YYYY-MM-DD). Default is today.
    """
    try:
        user_id = get_user_id(config)
        date_obj = parse_date(date)
        date_display = date_obj.strftime("%Y-%m-%d")

        db = await get_db()
        result = await db.weights.delete_one({"user_id": user_id, "date": date_obj})
        
        if result.deleted_count > 0:
            return f"✅ Weight deleted for {date_display}"
        else:
            return f"No weight entry found for {date_display} to delete."
            
    except Exception as e:
        return f"Error deleting weight: {str(e)}"

@tool
async def get_weight_history(days: int = 30, config: RunnableConfig = None) -> str:
    """
    Retrieves the user's weight history for the last specified number of days (defaults to 30 days).
    """
    try:
        user_id = get_user_id(config)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        db = await get_db()
        cursor = db.weights.find({"user_id": user_id, "date": {"$gte": cutoff_date}}).sort("date", 1)
        
        history = []
        async for doc in cursor:
            date_str = doc["date"].strftime("%Y-%m-%d")
            weight = doc["weight"]
            unit = doc.get("unit", "kg")
            history.append(f"- {date_str}: {weight} {unit}")
            
        if not history:
            return f"No weight entries found in the last {days} days."
            
        return f"Weight history for the last {days} days:\n" + "\n".join(history)
            
    except Exception as e:
        return f"Error retrieving weight history: {str(e)}"
