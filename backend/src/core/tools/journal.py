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
    
    # Get current UTC time for timestamp
    now_utc = datetime.now(timezone.utc)
    timestamp_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Target directory: base_path/user_id/agent_name
    target_dir = os.path.join(base_path, str(user_id), agent_name)
    
    # 3. Ensure the nested directory structure exists
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        return f"Error: Failed to create journal directory structure. {e}"

    # Target file: journal.txt
    target_file = os.path.join(target_dir, "journal.txt")

    # 4. Append the message format
    entry = f"[{timestamp_str}]\n{message}\n{'-' * 40}\n"

    try:
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(entry)
        return f"Successfully saved journal entry for agent '{agent_name}'."
    except Exception as e:
        return f"Error: Failed to write to journal file. {e}"

@tool
async def read_journal(
    agent_name: Annotated[str, "The agent/sub-journal name to read from (e.g., 'mind_buddy/gratitude'). Use 'mind_buddy' to read all mind_buddy sub-journals."],
    days: Annotated[int, "Number of past days to read. Defaults to 7."] = 7,
    config: RunnableConfig = None
) -> str:
    """
    Reads recent journal entries for the given agent_name.
    If agent_name is a parent (e.g., 'mind_buddy'), reads from all sub-journals underneath it.
    Returns the entries as a single text block, newest first.
    """
    user_id = config.get("configurable", {}).get("user_id") if config else None
    if not user_id:
        return "Error: Could not determine user ID from context."

    db = await get_db()
    settings = await db.system_settings.find_one({})
    base_path = "data/journal"
    if settings and settings.get("journal_base_path"):
        base_path = settings["journal_base_path"]

    agent_dir = os.path.join(base_path, str(user_id), agent_name)
    if not os.path.isdir(agent_dir):
        return f"No journal entries found for '{agent_name}'."

    # Collect all journal.txt files under agent_dir
    file_paths: list[tuple[str, str]] = []  # (sub_journal_label, filepath)

    for root, dirs, files in os.walk(agent_dir):
        for f in files:
            if f == "journal.txt":
                rel = os.path.relpath(root, agent_dir)
                label = rel if rel != "." else agent_name
                file_paths.append((label, os.path.join(root, f)))

    if not file_paths:
        return f"No journal entries found for '{agent_name}'."

    file_paths.sort(key=lambda x: x[0])

    entries = []
    for label, filepath in file_paths:
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                content = fh.read().strip()
            entries.append(f"--- [{label}] ---\n{content}")
        except Exception:
            continue

    if not entries:
        return f"No readable journal entries found for '{agent_name}'."

    return "\n\n".join(entries)

@tool
async def list_sub_journals(
    agent_name: Annotated[str, "The parent agent name to list sub-journals for (e.g., 'mind_buddy')."],
    config: RunnableConfig = None
) -> str:
    """
    Lists all existing sub-journal names for the given agent and user.
    Use this BEFORE writing a journal entry to check if a matching sub-journal
    already exists, so you can avoid creating duplicates.
    Returns a list of sub-journal folder names, or a message if none exist yet.
    """
    user_id = config.get("configurable", {}).get("user_id") if config else None
    if not user_id:
        return "Error: Could not determine user ID from context."

    db = await get_db()
    settings = await db.system_settings.find_one({})
    base_path = "data/journal"
    if settings and settings.get("journal_base_path"):
        base_path = settings["journal_base_path"]

    agent_dir = os.path.join(base_path, str(user_id), agent_name)
    if not os.path.isdir(agent_dir):
        return f"No sub-journals found for '{agent_name}'. This user has no journal entries yet."

    # List immediate subdirectories (sub-journals)
    sub_journals = []
    for entry in sorted(os.listdir(agent_dir)):
        full_path = os.path.join(agent_dir, entry)
        if os.path.isdir(full_path):
            sub_journals.append(entry)

    if not sub_journals:
        return f"No sub-journals found under '{agent_name}'. Any new entry will create the first sub-journal."

    return f"Existing sub-journals for '{agent_name}': {', '.join(sub_journals)}"

__all__ = ["append_to_journal", "read_journal", "list_sub_journals"]
