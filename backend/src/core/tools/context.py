from typing import List, Annotated
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from src.core.database.ops import set_user_state

@tool
async def list_agents(config: RunnableConfig) -> str:
    """
    Lists all available AI assistant agents that the user can switch to.
    Use this when the user asks what you can do or what bots are available.
    """
    allowed_agents = config.get("configurable", {}).get("allowed_agents", ["general"])
    
    agent_descriptions = {
        "general": "General chat, routing, and answering questions",
        "weight": "Log, update, and track body weight",
        "profile": "Background data entry for saving user preferences and facts",
        "remind": "Create, manage, and delete recurring reminders or tasks",
        "mind": "A gentle mental health companion for journaling, mood tracking, and emotional support"
    }
    
    response = "Available Agents:\n"
    for ag in allowed_agents:
        if ag in agent_descriptions:
            response += f"- {ag}: {agent_descriptions[ag]}\n"
            
    return response.strip()

@tool
async def set_active_agent(
    agent_name: Annotated[str, "The name of the agent to switch to: 'general', 'weight', 'profile', 'remind', or 'mind'"],
    config: RunnableConfig
) -> str:
    """
    Switches the user's active agent environment to the requested agent.
    Use this when the user explicitly asks to switch modes, e.g., 'switch to weight tracker' or 'I want to set a reminder'.
    """
    allowed_agents = config.get("configurable", {}).get("allowed_agents", ["general"])
    
    if agent_name not in allowed_agents:
        return f"Error: '{agent_name}' is not allowed on this integration. Allowed options are: {', '.join(allowed_agents)}"
        
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
         return "Error: Could not determine user ID to switch state."
         
    await set_user_state(int(user_id), agent_name)
    return f"Successfully switched active agent to '{agent_name}'. Please tell the user they are now in the {agent_name} mode."
