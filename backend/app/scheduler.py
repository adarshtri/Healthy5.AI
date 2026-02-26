import asyncio
from datetime import datetime, timedelta
from .database import get_db, get_chat_history
from .models import ReminderInstance, ChatMessage
from .agents.graph import general_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bson import ObjectId

async def generate_upcoming_instances():
    """Generates ReminderInstances for the next 24 hours based on active configs."""
    while True:
        try:
            db = await get_db()
            now = datetime.utcnow()
            tomorrow = now + timedelta(days=1)
            
            # Get all active configs
            configs_cursor = db.reminder_configs.find({"is_active": True})
            async for config in configs_cursor:
                config_id = str(config["_id"])
                rec_type = config.get("recurrence_type", "daily")
                
                if rec_type == "daily":
                    if not config.get("time_of_day"):
                         continue
                    time_parts = config["time_of_day"].split(":")
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    
                    # Check today and tomorrow
                    for day_offset in [0, 1]:
                        target_date = now + timedelta(days=day_offset)
                        target_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        
                        # Does it match the days_of_week?
                        if config.get("days_of_week"):
                            if target_time.weekday() not in config["days_of_week"]:
                                continue
                                
                        # Is it in the future but within 24 hours?
                        if now <= target_time <= tomorrow:
                            # Check if this instance already exists avoiding duplicates
                            existing = await db.reminder_instances.find_one({
                                "config_id": config_id,
                                "scheduled_time": target_time
                            })
                            if not existing:
                                new_instance = ReminderInstance(
                                    config_id=config_id,
                                    user_id=config["user_id"],
                                    title=config["title"],
                                    action_type=config.get("action_type", "message"),
                                    target_user_id=config.get("target_user_id"),
                                    scheduled_time=target_time
                                )
                                await db.reminder_instances.insert_one(new_instance.model_dump())
                                
                elif rec_type == "interval":
                    interval_mins = config.get("interval_minutes")
                    if not interval_mins or interval_mins <= 0:
                        continue
                        
                    # Find latest instance for this config
                    latest_instance = await db.reminder_instances.find_one(
                        {"config_id": config_id},
                        sort=[("scheduled_time", -1)]
                    )
                    
                    if latest_instance and latest_instance["scheduled_time"] > now - timedelta(days=1):
                        next_time = latest_instance["scheduled_time"] + timedelta(minutes=interval_mins)
                    else:
                        # Start from next nice interval boundary from config creation or now
                        next_time = now + timedelta(minutes=interval_mins)
                        
                    while next_time <= tomorrow:
                        if next_time >= now:
                            existing = await db.reminder_instances.find_one({
                                "config_id": config_id,
                                "scheduled_time": next_time
                            })
                            if not existing:
                                new_instance = ReminderInstance(
                                    config_id=config_id,
                                    user_id=config["user_id"],
                                    title=config["title"],
                                    action_type=config.get("action_type", "message"),
                                    target_user_id=config.get("target_user_id"),
                                    scheduled_time=next_time
                                )
                                await db.reminder_instances.insert_one(new_instance.model_dump())
                        next_time += timedelta(minutes=interval_mins)
                            
        except Exception as e:
            print(f"Error in generate_upcoming_instances: {e}")
            
        await asyncio.sleep(60)  # Run every minute to catch newly created configs

async def poll_and_notify():
    """Polls for due reminders and sends Telegram messages."""
    while True:
        try:
            db = await get_db()
            now = datetime.utcnow()
            
            # Find all pending instances that are due (scheduled_time <= now)
            due_instances = db.reminder_instances.find({
                "status": "pending",
                "scheduled_time": {"$lte": now}
            })
             
            async for instance in due_instances:
                # Provide a 2 hours window. Or else it's expired
                two_hours_ago = now - timedelta(hours=2)
                if instance["scheduled_time"] < two_hours_ago:
                    await db.reminder_instances.update_one(
                        {"_id": instance["_id"]},
                        {"$set": {"status": "expired"}}
                    )
                    continue
                
                try:
                    chat_target_id = instance.get("target_user_id") or instance["user_id"]
                    
                    if instance.get("action_type") == "agent":
                        # --- Agentic Execution ---
                        try:
                            # Fetch history so agent has context. Use target history if applicable.
                            history_models = await get_chat_history(chat_target_id, limit=10)
                            history_messages = []
                            for m in history_models:
                                if m.sender == "user":
                                    history_messages.append(HumanMessage(content=m.text))
                                elif m.sender == "bot" and m.text and m.text.strip():
                                    history_messages.append(AIMessage(content=m.text))
                                    
                            agenda = f"You are running as a background cron job. It is time for the user's scheduled task: '{instance['title']}'. Review their profile and history, then generate a personalized message fulfilling this task to send directly to them right now."
                            sys_msg = SystemMessage(content=agenda)
                            
                            input_messages = history_messages + [sys_msg]
                            
                            # We use general_agent to avoid tool restrictions of weight/profile subgraphs
                            result = general_agent({"messages": input_messages})
                            bot_response_text = result["messages"][0].content
                            
                            # Fetch token from targeted user's profile
                            target_profile = await db.profiles.find_one({"user_id": chat_target_id})
                            bot_token = target_profile.get("bot_token") if target_profile else None
                            bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
                            
                            async with Bot(token=bot_token) as dyn_bot:
                                msg = await dyn_bot.send_message(
                                    chat_id=chat_target_id,
                                    text=f"🤖 **Auto-Agent:**\n{bot_response_text}"
                                )
                            
                            # Log the bot's autonomous message to history
                            bot_hist_msg = ChatMessage(
                                user_id=chat_target_id, 
                                sender="bot", 
                                text=bot_response_text,
                                context="agent_reminder"
                            )
                            await db.chat_history.insert_one(bot_hist_msg.model_dump())
                        except Exception as ai_e:
                            print(f"Failed to execute agentic reminder: {ai_e}")
                            continue
                    else:
                        # --- Standard Static Message ---
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [
                                InlineKeyboardButton(text="✅ Done", callback_data=f"rem:done:{str(instance['_id'])}"),
                                InlineKeyboardButton(text="⏭️ Skip", callback_data=f"rem:skip:{str(instance['_id'])}")
                            ]
                        ])
                        
                        # Fetch token from targeted user's profile
                        target_profile = await db.profiles.find_one({"user_id": chat_target_id})
                        bot_token = target_profile.get("bot_token") if target_profile else None
                        bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
                        
                        async with Bot(token=bot_token) as dyn_bot:
                            msg = await dyn_bot.send_message(
                                chat_id=chat_target_id,
                                text=f"⏰ **Reminder:** {instance['title']}",
                                reply_markup=keyboard
                            )
                        
                    # Update status to notified
                    await db.reminder_instances.update_one(
                        {"_id": instance["_id"]},
                        {"$set": {"status": "notified", "telegram_message_id": msg.message_id}}
                    )
                except Exception as e:
                    print(f"Failed to send reminder to {chat_target_id}: {e}")
                    
        except Exception as e:
            print(f"Error in poll_and_notify: {e}")
            
        await asyncio.sleep(60)  # Run every minute

async def check_timeouts():
    """Marks 'notified' items as 'expired' if untouched for > 2 hours."""
    while True:
        try:
            db = await get_db()
            now = datetime.utcnow()
            two_hours_ago = now - timedelta(hours=2)
            
            # Find all notified instances that are > 2 hours old
            expired_instances = db.reminder_instances.find({
                "status": "notified",
                "scheduled_time": {"$lte": two_hours_ago}
            })
            
            async for instance in expired_instances:
                 await db.reminder_instances.update_one(
                     {"_id": instance["_id"]},
                     {"$set": {"status": "expired"}}
                 )
                 
                 try:
                     # Remove the buttons from the telegram message
                     if instance.get("telegram_message_id"):
                          # We need a bot to edit messages. Let's find the correct token.
                          target_user_id = instance.get("target_user_id") or instance["user_id"]
                          target_profile = await db.profiles.find_one({"user_id": target_user_id})
                          bot_token = target_profile.get("bot_token") if target_profile else None
                          bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")

                          async with Bot(token=bot_token) as dyn_bot:
                              await dyn_bot.edit_message_reply_markup(
                                  chat_id=target_user_id,
                                  message_id=instance["telegram_message_id"],
                                  reply_markup=None
                              )
                              await dyn_bot.send_message(
                                  chat_id=target_user_id,
                                  text=f"⚠️ You missed your reminder: {instance['title']}"
                              )
                 except Exception as e:
                      pass
                      
        except Exception as e:
            print(f"Error in check_timeouts: {e}")
            
        await asyncio.sleep(60 * 5)  # Run every 5 minutes

def start_scheduler():
    """Starts the background asyncio tasks."""
    asyncio.create_task(generate_upcoming_instances())
    asyncio.create_task(poll_and_notify())
    asyncio.create_task(check_timeouts())
