from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from src.core.database import get_chat_history, get_db
from src.core.database.ops import save_chat_message
from src.events.schemas import ReceivedMessage
from src.core.agents.graph import AgentState

class ContextManager:
    """
    Handles extracting context from the database, transforming messages, 
    and preparing the AgentState for the LangGraph agent loop.
    """
    
    @staticmethod
    async def build_user_context(event: ReceivedMessage, limit: int = 10) -> AgentState:
        """
        Fetches the recent message history for the specified user and builds the
        AgentState dictionary required by the AI loop.
        """
        # 1. Save the newest incoming user message to the database
        await save_chat_message(
            source_platform=event.source_platform,
            source_id=event.source_id,
            sender="user",
            text=event.text_content
        )
        
        # 2. Fetch historical context for this user
        history = await get_chat_history(event.source_platform, event.source_id, limit=limit)
        
        # 3. Convert DB ChatMessages into LangChain BaseMessage objects
        formatted_messages: List[BaseMessage] = []
        for msg in history:
            if msg.sender == "user":
                formatted_messages.append(HumanMessage(content=msg.text))
            else:
                formatted_messages.append(AIMessage(content=msg.text))
                
        # 4. Fetch the user's active agent state (defaults to "general" if missing)
        db = await get_db()
        try:
            uid = int(event.source_id)
        except ValueError:
            uid = event.source_id
            
        user_profile = await db.profiles.find_one({"user_id": uid})
        active_agent = "general"
        if user_profile and "active_agent" in user_profile:
            active_agent = user_profile["active_agent"]
            
        # Fetch allowed agents for the specific integration token
        allowed_agents = ["general"]
        if event.bot_token_or_id:
            system_user = await db.system_users.find_one({
                "integrations": {
                    "$elemMatch": {
                        "token": event.bot_token_or_id
                    }
                }
            })
            if system_user:
                for intg in system_user.get("integrations", []):
                    if intg.get("token") == event.bot_token_or_id:
                        allowed_agents = intg.get("allowed_agents", ["general"])
                        break
        
        print(f"[ContextManager] User {event.source_id} allowed_agents from DB: {allowed_agents}")

        # 5. Append the newest incoming message directly to the state
        formatted_messages.append(HumanMessage(content=event.text_content))

        state: AgentState = {
            "messages": formatted_messages,
            "active_agent": active_agent,
            "allowed_agents": allowed_agents
        }
        
        return state
