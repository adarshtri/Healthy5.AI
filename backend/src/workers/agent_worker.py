import os
import asyncio
from dotenv import load_dotenv

# Adjust imports to new core structure
from src.core.agents.context import ContextManager
from src.core.agents.graph import get_compiled_graph
from src.events.schemas import ReceivedMessage, DeliverMessage
from src.events.broker import get_outgoing_queue
from src.core.database.ops import save_chat_message

load_dotenv()

def process_incoming(event_dict: dict):
    """
    This runs inside the RQ worker synchronously, so we must run our 
    async LangGraph code using asyncio.run.
    """
    event = ReceivedMessage(**event_dict)
    print(f"[Agent Worker] Received event from {event.source_platform} user {event.source_id}")
    
    # Run the core logic asynchronously 
    asyncio.run(_async_process_incoming(event))


async def _async_process_incoming(event: ReceivedMessage):
    # 1. Prepare State via ContextManager
    # ContextManager already saves the incoming user message to DB
    state = await ContextManager.build_user_context(event)
    
    # 2. Extract the routing destination (agent spec) from the user's active configuration
    active_agent = state.get("active_agent", "general")
    allowed_agents = state.get("allowed_agents", ["general"])
    
    if active_agent not in allowed_agents:
        active_agent = allowed_agents[0] if allowed_agents else "general"
        print(f"[{event.source_id}] Active agent not in allowed_agents. Falling back to: {active_agent}")

    print(f"[{event.source_id}] Routing to Agent Spec: {active_agent}")
    
    # 3. Compile/Fetch the specific agent Graph dynamically
    try:
        compiled_graph = get_compiled_graph(active_agent)
    except ValueError as e:
        print(f"[Agent Worker Error] {e} Falling back to general.")
        compiled_graph = get_compiled_graph("general")

    # 4. Invoke the Graph with the state (LangGraph ainvoke is async)
    print(f"[{event.source_id}] Generating response for: {event.text_content}")
    # Using config to pass user_id down for tools that need to query the database (e.g. Profile Agent)
    try:
        uid = int(event.source_id)
    except ValueError:
        uid = event.source_id
        
    config = {
        "configurable": {
            "user_id": uid, 
            "bot_token": event.bot_token_or_id,
            "allowed_agents": allowed_agents
        }
    }
    result = await compiled_graph.ainvoke(state, config=config)
    
    # 5. Extract the AI's response message
    final_message_obj = result["messages"][-1]
    final_message = final_message_obj.content
    
    # 6. Save the outbound message from the bot
    await save_chat_message(event.source_platform, event.source_id, "bot", final_message)
    
    # 7. Push a DeliverMessage event to the outgoing queue
    outgoing_event = DeliverMessage(
        target_platform=event.source_platform,
        target_id=event.source_id,
        bot_token_or_id=event.bot_token_or_id,
        text_content=final_message
    )
    
    queue = get_outgoing_queue()
    queue.enqueue("src.workers.egress_worker.process_outgoing", outgoing_event.model_dump())
    print(f"[Agent Worker] Queued response for Delivery: {final_message[:50]}...")

