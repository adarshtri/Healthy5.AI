import os
from datetime import datetime, timezone
from typing import Annotated
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from src.core.database import get_db

@tool
async def append_to_journal(
    agent_name: Annotated[str, "The name or category of the agent (e.g., 'weight', 'mental_health', 'diet'). Used to categorize the journal entry."],
    message: Annotated[str, "The message or data entry to append to the user's journal."],
    config: RunnableConfig
) -> str:
    """
    Appends a text entry to the user's local file-based journal.
    The entries are segregated automatically by the agent's name and the current UTC date.
    Use this tool whenever you need to save information, log a user's progress, or record an event.
    """
    # 1. Extract context from config
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        return "Error: Could not determine user ID from context. Journal entry not saved."

    # 2. Determine paths and directories
    db = await get_db()
    settings = await db.system_settings.find_one({})
    base_path = "data/journal"
    if settings and settings.get("journal_base_path"):
        base_path = settings["journal_base_path"]
    
    # Get current UTC time for date segregation and timestamp
    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%Y-%m-%d")
    timestamp_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Target directory: base_path/agent_name/YYYY-MM-DD
    target_dir = os.path.join(base_path, agent_name, date_str)
    
    # 3. Ensure the nested directory structure exists
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        return f"Error: Failed to create journal directory structure. {e}"

    # Target file: user_id.txt (or profile name if we wanted, but user_id is safer)
    target_file = os.path.join(target_dir, f"{user_id}.txt")

    # 4. Append the message format
    entry = f"[{timestamp_str}]\n{message}\n{'-' * 40}\n"

    try:
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(entry)
        return f"Successfully saved journal entry for agent '{agent_name}' on date {date_str}."
    except Exception as e:
        return f"Error: Failed to write to journal file. {e}"

__all__ = ["append_to_journal"]
