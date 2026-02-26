from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from datetime import datetime
from ..database import get_db
from ..models import ReminderConfig

def get_user_id(config: RunnableConfig) -> int:
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        raise ValueError("User ID not found in context.")
    return int(user_id)

@tool
async def create_reminder(
    title: str,
    action_type: str = "message",
    target_name: str = None,
    recurrence_type: str = "daily",
    time_of_day: str = None, 
    days_of_week: list[int] = None, 
    interval_minutes: int = None,
    config: RunnableConfig = None
) -> str:
    """
    Creates a recurring reminder for the user or another person.
    Args:
        title (str): Short description of what to remind about (e.g., "Eat Breakfast", "Drink water") or a prompt for the agent.
        action_type (str): Either "message" (default) for static text or "agent" for dynamic prompt execution.
        target_name (str): The name of another person to send the reminder to (e.g., "Rashi"). If for oneself, leave None.
        recurrence_type (str): Either "daily" or "interval".
        time_of_day (str): For "daily". Time in HH:MM format (24-hour clock), e.g., "09:00".
        days_of_week (list[int]): For "daily". Days to remind: 0=Monday, 6=Sunday. Pass an empty list [] for EVERY day.
        interval_minutes (int): For "interval". Minimum minutes between reminders (e.g., 60 for every hour, 30 for every half hour).
    """
    try:
        user_id = get_user_id(config)
        if days_of_week is None:
            days_of_week = []
            
        if recurrence_type not in ["daily", "interval"]:
             return "Error: recurrence_type must be 'daily' or 'interval'."
             
        if recurrence_type == "daily":
            if not time_of_day:
                return "Error: time_of_day must be provided for daily reminders."
            try:
                datetime.strptime(time_of_day, "%H:%M")
            except ValueError:
                return "Error: time_of_day must be precisely in HH:MM 24-hour format (e.g., '09:00', '15:30')."
        elif recurrence_type == "interval":
             if interval_minutes is None or interval_minutes <= 0:
                  return "Error: interval_minutes must be a positive integer for interval reminders."
                  
        target_user_id = None
        db = await get_db()
        
        if target_name:
            target_profile = await db.profiles.find_one({"name": {"$regex": f"^{target_name}$", "$options": "i"}})
            if target_profile:
                target_user_id = target_profile["user_id"]
            else:
                return f"Error: Could not find a user profile with the name '{target_name}'. Ensure they have interacted with the bot and set their profile name before trying to schedule reminders for them."

        reminder = ReminderConfig(
            user_id=user_id,
            title=title,
            action_type=action_type,
            target_user_id=target_user_id,
            recurrence_type=recurrence_type,
            time_of_day=time_of_day,
            days_of_week=days_of_week,
            interval_minutes=interval_minutes
        )
        
        await db.reminder_configs.insert_one(reminder.model_dump())
        
        if recurrence_type == "daily":
             days_str = "every day" if not days_of_week else f"on days {days_of_week} (0=Mon, 6=Sun)"
             return f"✅ Reminder '{title}' successfully set for {time_of_day} {days_str}."
        else:
             return f"✅ Reminder '{title}' successfully set for every {interval_minutes} minutes."
    except Exception as e:
        return f"Error setting reminder: {str(e)}"

@tool
async def list_reminders(config: RunnableConfig = None) -> str:
    """
    Lists all active recurring reminders for the user.
    """
    try:
        user_id = get_user_id(config)
        db = await get_db()
        
        cursor = db.reminder_configs.find({"user_id": user_id, "is_active": True})
        reminders = await cursor.to_list(length=100)
        
        if not reminders:
            return "You have no active reminders set."
            
        lines = ["Active Reminders:"]
        for r in reminders:
            if r.get('recurrence_type', 'daily') == 'interval':
                 lines.append(f"- '{r['title']}' every {r['interval_minutes']} minutes")
            else:
                 days = "Every day" if not r.get('days_of_week') else f"Days: {r['days_of_week']}"
                 lines.append(f"- '{r['title']}' at {r['time_of_day']} ({days})")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing reminders: {str(e)}"

@tool
async def delete_reminder(title: str, config: RunnableConfig = None) -> str:
    """
    Deletes (deactivates) a recurring reminder by exactly matching its title. Use list_reminders first to get the exact title.
    """
    try:
        user_id = get_user_id(config)
        db = await get_db()
        
        # 1. Deactivate the config
        config_doc = await db.reminder_configs.find_one_and_update(
            {"user_id": user_id, "title": title, "is_active": True},
            {"$set": {"is_active": False}}
        )
        
        if config_doc:
            # 2. Cleanup all future pending instances for this config
            await db.reminder_instances.delete_many({
                "config_id": str(config_doc["_id"]),
                "status": {"$in": ["pending", "notified"]} 
            })
            return f"✅ Reminder '{title}' and its upcoming occurrences have been successfully deleted."
        else:
            return f"❌ Could not find an active reminder named '{title}'. Please check the exact title using list_reminders."
    except Exception as e:
        return f"Error deleting reminder: {str(e)}"
