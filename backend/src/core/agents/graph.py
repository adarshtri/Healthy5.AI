import os
from datetime import datetime
from typing import Annotated, Literal, TypedDict, Union

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, SystemMessage, FunctionMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig

from src.core.agents.spec import AGENT_SPECS, AgentSpec
from src.core.tools.profile import get_user_profile

import logging
logger = logging.getLogger(__name__)

# --- State Definition ---
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    active_agent: str  # Tracks who handled the last turn: "weight", "profile", "general"
    allowed_agents: list[str]

# --- LLM Setup ---
# LLM is now dynamically instantiated per-invocation inside `call_model` to read up-to-date db settings.

# --- Helper: Context Filtering ---
def filter_messages(messages: list[BaseMessage], active_agent: str) -> list[BaseMessage]:
    filtered = []
    for msg in messages:
        # Always include System, Human, and Tool messages
        if msg.type in ["system", "human", "user", "tool"]:
            filtered.append(msg)
        elif msg.type == "ai":
            # Keep AI messages tracked to this agent, or those with no specific name tag
            name = getattr(msg, "name", None)
            if not name or name == active_agent:
                filtered.append(msg)
    return filtered

# --- Generic Subgraph Builder ---
def build_agent_graph(spec_name: str) -> 'CompiledStateGraph':
    """
    Dynamically builds a LangGraph based on the AgentSpec configuration.
    """
    spec = AGENT_SPECS.get(spec_name)
    if not spec:
        raise ValueError(f"Agent spec '{spec_name}' not found.")

    async def call_model(state: AgentState, config: RunnableConfig):
        from src.core.database import get_db
        db = await get_db()
        settings = await db.system_settings.find_one({})
        
        model_source = None
        ollama_model = None
        groq_model = None
        groq_api_key = None
        
        if settings:
            model_source = settings.get("model_source", "cloud")
            groq_model = settings.get("groq_model", groq_model)
            ollama_model = settings.get("ollama_model", ollama_model)
            groq_api_key = settings.get("groq_api_key")
            
        if model_source == "cloud" or model_source == "GROQ":
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                api_key=groq_api_key, 
                model_name=groq_model, 
                temperature=0
            )
        else:
            from langchain_ollama import ChatOllama
            llm = ChatOllama(model=ollama_model, temperature=0)

        # Only bind tools if the spec calls for them
        if spec.tools:
            model = llm.bind_tools(spec.tools)
        else:
            model = llm

        all_msgs = state["messages"]
        filtered = filter_messages(all_msgs, spec.name)
        
        # Format the system prompt dynamically based on the Agent Spec requirements
        sys_prompt_text = spec.system_prompt
        
        if "{current_date}" in sys_prompt_text:
             sys_prompt_text = sys_prompt_text.replace("{current_date}", datetime.now().strftime("%Y-%m-%d"))
        
        if spec.use_profile_context:
            user_id = config.get("configurable", {}).get("user_id")
            profile_text = "No profile found."
            if user_id:
                profile_data = await get_user_profile(int(user_id))
                if profile_data:
                    profile_text = f"Name: {profile_data.get('name')}, Age: {profile_data.get('age')}\nMemories: {profile_data.get('memories')}\nPreferences: {profile_data.get('preferences')}"
            
            sys_prompt_text = sys_prompt_text.replace("{profile_text}", profile_text)

        system_msg = SystemMessage(content=sys_prompt_text)
        
        response = await model.ainvoke([system_msg] + filtered)
        response.name = spec.name
        return {"messages": [response], "active_agent": spec.name}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent_model", call_model)
    
    workflow.add_edge(START, "agent_model")

    if spec.tools:
         workflow.add_node("agent_tools", ToolNode(spec.tools))
         
         def should_continue(state: AgentState):
              messages = state["messages"]
              last_message = messages[-1]
              if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                   return "agent_tools"
              return END
              
         workflow.add_conditional_edges("agent_model", should_continue)
         workflow.add_edge("agent_tools", "agent_model")
    else:
         workflow.add_edge("agent_model", END)
         
    return workflow.compile()

# --- Pre-compiled Generic Agents cache ---
_compiled_graphs = {}
def get_compiled_graph(spec_name: str):
    if spec_name not in _compiled_graphs:
        _compiled_graphs[spec_name] = build_agent_graph(spec_name)
    return _compiled_graphs[spec_name]

__all__ = ["get_compiled_graph", "AgentState"]
