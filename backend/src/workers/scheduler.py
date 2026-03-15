import asyncio
import os
from datetime import datetime, timedelta
from src.core.database import get_db, get_chat_history
from src.core.models import ReminderInstance, ChatMessage
from bson import ObjectId

# For EDA, we don't import Bot here. We push to queues.
from src.events.broker import get_outgoing_queue, get_incoming_queue
from src.events.schemas import DeliverMessage, ReceivedMessage


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
                                    bot_token=config.get("bot_token"),
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
                                    bot_token=config.get("bot_token"),
                                    target_user_id=config.get("target_user_id"),
                                    scheduled_time=next_time
                                )
                                await db.reminder_instances.insert_one(new_instance.model_dump())
                        next_time += timedelta(minutes=interval_mins)
                            
        except Exception as e:
            print(f"Error in generate_upcoming_instances: {e}")
            
        await asyncio.sleep(60)  # Run every minute


async def poll_and_notify():
    """Polls for due reminders and publishes events to queues."""
    out_queue = get_outgoing_queue()
    in_queue = get_incoming_queue()
    
    while True:
        try:
            db = await get_db()
            now = datetime.utcnow()
            
            # Find all pending instances that are due
            due_instances = db.reminder_instances.find({
                "status": "pending",
                "scheduled_time": {"$lte": now}
            })
             
            async for instance in due_instances:
                # Provide a 2 hours window
                two_hours_ago = now - timedelta(hours=2)
                if instance["scheduled_time"] < two_hours_ago:
                    await db.reminder_instances.update_one(
                        {"_id": instance["_id"]},
                        {"$set": {"status": "expired"}}
                    )
                    continue
                
                try:
                    chat_target_id = instance.get("target_user_id") or instance["user_id"]
                    
                    # Direct token from the instance > target_profile > default fallback
                    bot_token = instance.get("bot_token")
                    if not bot_token:
                        target_profile = await db.profiles.find_one({"user_id": chat_target_id})
                        bot_token = target_profile.get("bot_token", "default")
                    
                    if instance.get("action_type") == "agent":
                        # Push an event to the INCOMING queue to wake up an AI Agent worker
                        # We spoof a "system trigger" message for the LLM
                        sys_trigger = f"[System Trigger: Execute Scheduled Task] '{instance['title']}'"
                        
                        agent_event = ReceivedMessage(
                            source_platform="cron",
                            source_id=chat_target_id,
                            bot_token_or_id=bot_token,
                            text_content=sys_trigger
                        )
                        in_queue.enqueue("src.workers.agent_worker.process_incoming", agent_event.model_dump())
                    else:
                        # Push directly to OUTGOING queue
                        # Note: Aiogram inline keyboards would be serialized in 'raw_payload' in a full implementation,
                        # for now we send plain text as a proof of concept of the decoupled flow.
                        out_event = DeliverMessage(
                            target_platform="telegram",
                            target_id=chat_target_id,
                            bot_token_or_id=bot_token,
                            text_content=f"⏰ **Reminder:** {instance['title']}\n\n(Reply 'done' or 'skip')"
                        )
                        out_queue.enqueue("src.workers.egress_worker.process_outgoing", out_event.model_dump())
                        
                    # Update status to notified
                    await db.reminder_instances.update_one(
                        {"_id": instance["_id"]},
                        {"$set": {"status": "processing_async"}} # Changed from 'notified'
                    )
                except Exception as e:
                    print(f"Failed to queue reminder for {chat_target_id}: {e}")
                    
        except Exception as e:
            print(f"Error in poll_and_notify: {e}")
            
        await asyncio.sleep(60)


async def check_timeouts():
    """Cleanup old instances."""
    while True:
        try:
            db = await get_db()
            now = datetime.utcnow()
            two_hours_ago = now - timedelta(hours=2)
            
            # Find all processing instances that are > 2 hours old
            expired_instances = db.reminder_instances.find({
                "status": "processing_async",
                "scheduled_time": {"$lte": two_hours_ago}
            })
            
            async for instance in expired_instances:
                 await db.reminder_instances.update_one(
                     {"_id": instance["_id"]},
                     {"$set": {"status": "expired"}}
                 )
        except Exception as e:
            print(f"Error in check_timeouts: {e}")
            
        await asyncio.sleep(60 * 5)


def start_scheduler():
    """Starts the background asyncio tasks."""
    asyncio.create_task(generate_upcoming_instances())
    asyncio.create_task(poll_and_notify())
    asyncio.create_task(check_timeouts())
