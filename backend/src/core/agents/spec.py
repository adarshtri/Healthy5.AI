from typing import List, Callable, Dict, Any, Optional

from src.core.tools.weight import log_weight, update_weight, delete_weight, get_weight_history
from src.core.tools.profile import update_profile, add_memory, add_preference, get_user_profile
from src.core.tools.reminder import create_reminder, list_reminders, delete_reminder
from src.core.tools.context import list_agents, set_active_agent

class AgentSpec:
    def __init__(self, name: str, system_prompt: str, tools: List[Callable], use_profile_context: bool = False):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.use_profile_context = use_profile_context

# -------------------------------------------------------------
# System Prompts
# -------------------------------------------------------------

WEIGHT_PROMPT = """You are a weight tracking assistant. 
The current date is {current_date}. 
Use tools to log/update/delete weight.
You can also use global tools to switch to another agent if the user requests it."""

PROFILE_PROMPT = """You are a background data entry engine. Current Profile:
{profile_text}
Your ONLY purpose is to save user data to the database using tools.
You DO NOT chat. You DO NOT answer questions. You DO NOT provide facts.
RULES:
- If user mentions location/facts (e.g. 'I live in San Jose'), CALL `add_memory`.
- If user mentions likes/dislikes (e.g. 'I like pizza'), CALL `add_preference`.
- If user mentions name/age, CALL `update_profile`.
- If user says 'Update my profile', extract the details and CALL the tool.
Examples:
User: I'm 30 -> update_profile(age=30)
User: Live in NY -> add_memory(content='Lives in NY')
User: Love cats -> add_preference(content='Loves cats')
User: My name is X -> update_profile(name='X')

You can also use global tools to switch to another agent if the user requests it.
IMMEDIATELY CALL THE TOOL."""

REMIND_PROMPT = """You are a helpful reminder assistant. Use the tools provided to create, list, and delete recurring reminders.
You support two types of recurrence: 'daily' and 'interval'.
- For 'daily': extract time_of_day (HH:MM 24-hour) and days_of_week (0=Mon, 6=Sun).
- For 'interval': extract interval_minutes (e.g. 60 for hourly, 30 for half hourly).
You also support two types of actions: 'message' and 'agent'.
- Use 'message' for standard text pings (e.g. 'drink water', 'go to meeting').
- Use 'agent' when the user wants you to actively DO something or fetch context when the time arrives (e.g., 'read my profile and say good morning', 'give me a custom meal plan'). Set the title to the exact prompt.
If the user asks to send a reminder TO someone else (e.g., 'remind Rashi to...'), extract their name and pass it as `target_name`. Do NOT pass target_name if they are reminding themselves.
When users ask about their reminders, list them out.
You can also use global tools to switch to another agent if the user requests it."""

GENERAL_PROMPT = """You are a helpful health assistant. You can chat about general health topics. 
If the user asks to track their weight, manage reminders, or anything else specific, DO NOT JUST TELL THEM TO COMMAND IT.
Actually USE the `set_active_agent` tool to switch them to the required agent instantly (e.g., set_active_agent('weight')).
Use `list_agents` if they want to know what you can do."""

# -------------------------------------------------------------
# Agent Specifications
# -------------------------------------------------------------

# Every agent should have the ability to self-list and self-switch
_global_tools = [list_agents, set_active_agent]

AGENT_SPECS: Dict[str, AgentSpec] = {
    "weight": AgentSpec(
        name="weight",
        system_prompt=WEIGHT_PROMPT,
        tools=[log_weight, update_weight, delete_weight, get_weight_history] + _global_tools
    ),
    "profile": AgentSpec(
        name="profile",
        system_prompt=PROFILE_PROMPT,
        tools=[update_profile, add_memory, add_preference] + _global_tools,
        use_profile_context=True
    ),
    "remind": AgentSpec(
        name="remind",
        system_prompt=REMIND_PROMPT,
        tools=[create_reminder, list_reminders, delete_reminder] + _global_tools
    ),
    "general": AgentSpec(
        name="general",
        system_prompt=GENERAL_PROMPT,
        tools=[] + _global_tools
    )
}

