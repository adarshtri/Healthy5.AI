import os
import asyncio
from aiogram import Bot
from rq import get_current_job
from src.events.schemas import DeliverMessage

def process_outgoing(event_dict: dict):
    """
    Synchronous RQ worker entrypoint that runs our async sending logic.
    """
    event = DeliverMessage(**event_dict)
    print(f"[Egress Worker] Sending message to {event.target_platform} user {event.target_id}")

    if event.target_platform == "telegram":
        asyncio.run(_async_send_telegram(event))
    elif event.target_platform == "web":
        asyncio.run(_async_send_web(event))
    else:
        print(f"[Egress Worker] Unsupported platform: {event.target_platform}")

async def _async_send_web(event: DeliverMessage):
    import redis.asyncio as aioredis
    from src.core.database.connection import get_db

    db = await get_db()
    settings = await db.system_settings.find_one({}) or {}
    redis_url = settings.get("redis_url", "redis://localhost:6379/0")
    
    r = aioredis.from_url(redis_url, decode_responses=True)
    channel = f"web_chat_{event.target_id}"
    await r.publish(channel, event.text_content)
    await r.aclose()
    print(f"[Egress Worker] Published message to web channel: {channel}")


async def _async_send_telegram(event: DeliverMessage):
    """
    Instantiates an ephemeral Bot instance, sends the message, and closes the session.
    """
    bot = Bot(token=event.bot_token_or_id)
    try:
        await bot.send_message(
            chat_id=event.target_id,
            text=event.text_content
        )
        print(f"[Egress Worker] Successfully sent message to Telegram user {event.target_id}")
    except Exception as e:
        print(f"[Egress Worker] Failed to send message: {e}")
        # Retries would be handled natively by RQ or pushing back to queue
    finally:
        await bot.session.close()
