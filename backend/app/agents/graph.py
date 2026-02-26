import os
from datetime import datetime
from typing import Annotated, Literal, TypedDict, Union

from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, FunctionMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .tools import log_weight, update_weight, delete_weight, get_weight_history
from .profile_tools import update_profile, add_memory, add_preference, get_user_profile
from .reminder_tools import create_reminder, list_reminders, delete_reminder

from langchain_core.runnables import RunnableConfig

# --- State Definition ---
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    active_agent: str  # Tracks who handled the last turn: "weight", "profile", "general"

from langchain_groq import ChatGroq

# --- LLM Setup ---
model_source = os.getenv("MODEL_SOURCE", "OLLAMA_LOCAL")

if model_source == "GROQ":
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    llm = ChatGroq(
        model_name=groq_model, 
        temperature=0
    )
    print(f"INFO: Initialized ChatGroq ({groq_model})")
else:
    # Default to Ollama
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3"),
        temperature=0
    )
    print(f"INFO: Initialized ChatOllama ({os.getenv('OLLAMA_MODEL', 'llama3')})")

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

# --- Subgraph: Weight Agent ---
def create_weight_agent():
    tools = [log_weight, update_weight, delete_weight, get_weight_history]
    model = llm.bind_tools(tools)
    
    def call_weight_model(state: AgentState):
        all_msgs = state["messages"]
        filtered = filter_messages(all_msgs, "weight")
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        sys_msg = SystemMessage(content=f"You are a weight tracking assistant. The current date is {current_date}. Use tools to log/update/delete weight.")
        
        response = model.invoke([sys_msg] + filtered)
        response.name = "weight" 
        return {"messages": [response], "active_agent": "weight"}

    workflow = StateGraph(AgentState)
    workflow.add_node("weight_model", call_weight_model)
    workflow.add_node("weight_tools", ToolNode(tools))
    
    workflow.add_edge(START, "weight_model")
    
    def should_continue(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "weight_tools"
        return END

    workflow.add_conditional_edges("weight_model", should_continue)
    workflow.add_edge("weight_tools", "weight_model")
    
    return workflow.compile()

weight_graph = create_weight_agent()

# --- Subgraph: Profile Agent ---
def create_profile_agent():
    tools = [update_profile, add_memory, add_preference]
    model = llm.bind_tools(tools)
    
    async def call_profile_model(state: AgentState, config: RunnableConfig):
        all_msgs = state["messages"]
        filtered = filter_messages(all_msgs, "profile")
        
        user_id = config.get("configurable", {}).get("user_id")
        profile_text = "No profile found."
        if user_id:
            profile_data = await get_user_profile(int(user_id))
            if profile_data:
                profile_text = f"Name: {profile_data.get('name')}, Age: {profile_data.get('age')}\nMemories: {profile_data.get('memories')}\nPreferences: {profile_data.get('preferences')}"
        
        system_prompt = (
            f"You are a background data entry engine. Current Profile:\n{profile_text}\n"
            "Your ONLY purpose is to save user data to the database using tools.\n"
            "You DO NOT chat. You DO NOT answer questions. You DO NOT provide facts.\n"
            "RULES:\n"
            "- If user mentions location/facts (e.g. 'I live in San Jose'), CALL `add_memory`.\n"
            "- If user mentions likes/dislikes (e.g. 'I like pizza'), CALL `add_preference`.\n"
            "- If user mentions name/age, CALL `update_profile`.\n"
            "- If user says 'Update my profile', extract the details and CALL the tool.\n"
            "Examples:\n"
            "User: I'm 30 -> update_profile(age=30)\n"
            "User: Live in NY -> add_memory(content='Lives in NY')\n"
            "User: Love cats -> add_preference(content='Loves cats')\n"
             "User: My name is X -> update_profile(name='X')\n" 
            "IMMEDIATELY CALL THE TOOL."
        )
        
        response = await model.ainvoke([SystemMessage(content=system_prompt)] + filtered)
        response.name = "profile"
        return {"messages": [response], "active_agent": "profile"}

    workflow = StateGraph(AgentState)
    workflow.add_node("profile_model", call_profile_model)
    workflow.add_node("profile_tools", ToolNode(tools))
    
    workflow.add_edge(START, "profile_model")
    
    def should_continue(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "profile_tools"
        return END

    workflow.add_conditional_edges("profile_model", should_continue)
    workflow.add_edge("profile_tools", "profile_model")
    
    return workflow.compile()

profile_graph = create_profile_agent()


# --- Subgraph: Remind Agent ---
def create_remind_agent():
    tools = [create_reminder, list_reminders, delete_reminder]
    model = llm.bind_tools(tools)
    
    async def call_remind_model(state: AgentState, config: RunnableConfig):
        all_msgs = state["messages"]
        filtered = filter_messages(all_msgs, "remind")
        
        system_prompt = (
            "You are a helpful reminder assistant. Use the tools provided to create, list, and delete recurring reminders.\n"
            "You support two types of recurrence: 'daily' and 'interval'.\n"
            "- For 'daily': extract time_of_day (HH:MM 24-hour) and days_of_week (0=Mon, 6=Sun).\n"
            "- For 'interval': extract interval_minutes (e.g. 60 for hourly, 30 for half hourly).\n"
            "You also support two types of actions: 'message' and 'agent'.\n"
            "- Use 'message' for standard text pings (e.g. 'drink water', 'go to meeting').\n"
            "- Use 'agent' when the user wants you to actively DO something or fetch context when the time arrives (e.g., 'read my profile and say good morning', 'give me a custom meal plan'). Set the title to the exact prompt.\n"
            "If the user asks to send a reminder TO someone else (e.g., 'remind Rashi to...'), extract their name and pass it as `target_name`. Do NOT pass target_name if they are reminding themselves.\n"
            "When users ask about their reminders, list them out."
        )
        
        response = await model.ainvoke([SystemMessage(content=system_prompt)] + filtered)
        response.name = "remind"
        return {"messages": [response], "active_agent": "remind"}

    workflow = StateGraph(AgentState)
    workflow.add_node("remind_model", call_remind_model)
    workflow.add_node("remind_tools", ToolNode(tools))
    
    workflow.add_edge(START, "remind_model")
    
    def should_continue(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "remind_tools"
        return END

    workflow.add_conditional_edges("remind_model", should_continue)
    workflow.add_edge("remind_tools", "remind_model")
    
    return workflow.compile()

remind_graph = create_remind_agent()


# --- General Chat Agent ---

def general_agent(state: AgentState):
    """
    A simple chat node for general inquiries when no specific agent is active.
    """
    messages = state["messages"]
    sys_msg = SystemMessage(content="You are a helpful health assistant. You can chat about general health topics. If the user asks to track their weight or update their profile, politely ask them to use the /weight or /profile commands to switch modes.")
    response = llm.invoke([sys_msg] + messages)
    return {"messages": [response], "active_agent": "general"}

# We no longer compile a master graph here.
# We export the individual subgraphs and nodes explicitly.
__all__ = ["weight_graph", "profile_graph", "remind_graph", "general_agent", "AgentState"]
