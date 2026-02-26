import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from .agents.graph import weight_graph, profile_graph, remind_graph, general_agent
from .database import get_db, get_chat_history
from .database.ops import get_user_state, set_user_state
from .models import ChatMessage
from bson import ObjectId

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# We no longer instantiate a global Bot here.
# The Bot instance will be provided dynamically via the webhook payload context.
dp = Dispatcher()

# --- Command Handlers (Context Switching) ---

@dp.message(Command("start", "chat"))
async def cmd_chat(message: Message):
    await set_user_state(message.from_user.id, "general")
    await message.answer("👋 Hello! I am your Healthy5 AI assistant.\nYou are now in **General Chat** mode. \n\nCommands:\n/weight - Track your weight\n/profile - Update your profile\n/chat - General talk")

@dp.message(Command("weight"))
async def cmd_weight(message: Message):
    await set_user_state(message.from_user.id, "weight")
    await message.answer("⚖️ **Weight Tracking Mode Active**\nYou can now log inferences like:\n- 'I weigh 80kg today'\n- 'Delete my last weight entry'")

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    await set_user_state(message.from_user.id, "profile")
    await message.answer("👤 **Profile Edit Mode Active**\nYou can now tell me things like:\n- 'My name is John'\n- 'I live in San Jose'\n- 'I like eating apples'")

@dp.message(Command("remind"))
async def cmd_remind(message: Message):
    await set_user_state(message.from_user.id, "remind")
    await message.answer("⏰ **Reminder Mode Active**\nYou can now say things like:\n- 'Remind me to drink water every day at 14:00'\n- 'List my reminders'\n- 'Delete my breakfast reminder'")

# --- Callback Query Handler (Inline Buttons) ---
@dp.callback_query(lambda c: c.data and c.data.startswith("rem:"))
async def process_reminder_callback(callback_query: CallbackQuery):
    db = await get_db()
    
    parts = callback_query.data.split(":")
    action = parts[1]
    instance_id_str = parts[2]
    
    status_update = "completed" if action == "done" else "skipped"
    
    try:
         await db.reminder_instances.update_one(
             {"_id": ObjectId(instance_id_str)},
             {"$set": {"status": status_update}}
         )
         
         icon = "✅" if action == "done" else "⏭️"
         original_text = callback_query.message.text.replace("⏰ Reminder: ", "").replace("⏰ **Reminder:** ", "")
         await callback_query.bot.edit_message_text(
             text=f"{icon} {status_update.capitalize()}: {original_text}",
             chat_id=callback_query.from_user.id,
             message_id=callback_query.message.message_id,
             reply_markup=None
         )
         
         await callback_query.answer("Recorded!")
    except Exception as e:
         print(f"Callback error: {e}")
         await callback_query.answer("Failed to update.")

# --- Main Message Handler ---

@dp.message()
async def handle_message(message: Message):
    """
    Handles incoming messages using state-based routing.
    """
    user_id = message.from_user.id
    text = message.text.strip()
    db = await get_db()
    
    # 1. Idempotency Check (Prevent duplicate processing of same message_id)
    # Telegram sends retries if we don't respond quickly or crash.
    # We check if we already processed this message_id.
    existing_msg = await db.chat_history.find_one({
        "user_id": user_id, 
        "message_id": message.message_id
    })
    
    if existing_msg:
        # We must still return 200 OK to Telegram so it stops retrying
        return
        
    # 2. Fetch Active Agent State
    active_agent = await get_user_state(user_id)

    # 3. Fetch Chat History (last 10 messages)
    history_models = await get_chat_history(user_id, limit=10)
    
    history_messages = []
    for msg in history_models:
        if msg.sender == "user":
            history_messages.append(HumanMessage(content=msg.text))
        elif msg.sender == "bot":
            if msg.text and msg.text.strip():
                history_messages.append(AIMessage(content=msg.text))
            
    # 4. Log User Message 
    user_msg = ChatMessage(
        user_id=user_id, 
        sender="user", 
        text=text,
        message_id=message.message_id  # Store ID for idempotency
    )
    insert_result = await db.chat_history.insert_one(user_msg.model_dump())
    user_msg_id = insert_result.inserted_id

    # 5. Invoke Specific Agent Graph 
    config = {"configurable": {"thread_id": str(user_id), "user_id": user_id}}
    input_messages = history_messages + [HumanMessage(content=text)]
    input_state = {"messages": input_messages}
    
    try:
        if active_agent == "weight":
            result = await weight_graph.ainvoke(input_state, config=config)
            last_message = result["messages"][-1]
            response_text = last_message.content
        elif active_agent == "profile":
            result = await profile_graph.ainvoke(input_state, config=config)
            last_message = result["messages"][-1]
            response_text = last_message.content
        elif active_agent == "remind":
            result = await remind_graph.ainvoke(input_state, config=config)
            last_message = result["messages"][-1]
            response_text = last_message.content
        else:
            # Fallback to general agent
            result = general_agent({"messages": input_messages})
            response_text = result["messages"][0].content
    except Exception as e:
        response_text = "Sorry, I ran into an error processing your request."
        print(f"Error: {e}")
        result = {}

    
    # Extract context
    active_agent = result.get("active_agent", active_agent)
    
    # Update User Message Context
    if user_msg_id:
        await db.chat_history.update_one(
            {"_id": user_msg_id},
            {"$set": {"context": active_agent}}
        )

    # 4. Send Response (Split if too long)
    if response_text and response_text.strip():
        max_length = 4000
        for i in range(0, len(response_text), max_length):
            chunk = response_text[i:i+max_length]
            await message.answer(chunk)
            
        # 5. Log Bot Response with Context
        bot_msg = ChatMessage(
            user_id=user_id, 
            sender="bot", 
            text=response_text,
            context=active_agent
        )
        await db.chat_history.insert_one(bot_msg.model_dump())
    else:
        # Fallback if model returns empty content (e.g. only a tool call)
        # We don't want to log empty strings to the database history!
        pass
