from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import json
import asyncio
from sse_starlette.sse import EventSourceResponse
from src.gateway.api.auth import get_current_user
from src.events.schemas import ReceivedMessage
from src.events.broker import get_incoming_queue
from src.core.database.ops import get_chat_history
import os
import redis.asyncio as aioredis # Using aioredis from redis 4.2+ for async pubsub

router = APIRouter()

# Setup Redis connection for PubSub
# We will use get_redis_url() dynamically to avoid os.getenv

class ChatMessage(BaseModel):
    integration_token: str
    text: str
    session_id: str

@router.post("/message")
async def send_web_message(msg: ChatMessage, current_user: dict = Depends(get_current_user)):
    """
    Simulates a webhook from the web UI. Injects the message directly
    into the exact same event pipeline as Telegram messages.
    """
    try:
        # Create standard event
        event = ReceivedMessage(
            source_platform="web",
            source_id=msg.session_id, # Uses the user's session_id as their chat_id
            bot_token_or_id=msg.integration_token,
            text_content=msg.text,
            raw_payload=msg.model_dump()
        )
        
        # Push to the Message Bus (Redis Queue)
        queue = get_incoming_queue()
        queue.enqueue("src.workers.agent_worker.process_incoming", event.model_dump())
        
        return {"status": "ok", "delivered_to_queue": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{session_id}")
async def fetch_chat_history(session_id: str, skip: int = 0, current_user: dict = Depends(get_current_user)):
    """
    Fetches historical messages for the web chat interface with pagination support.
    """
    try:
        messages = await get_chat_history(
            source_platform="web", 
            source_id=session_id, 
            limit=20, 
            skip=skip
        )
        return {"status": "success", "messages": [m.model_dump() for m in messages]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream/{session_id}")
async def stream_chat_responses(session_id: str, request: Request):
    """
    Subscribes to the specific Redis PubSub channel for this session and
    streams agent replies down to the frontend using Server-Sent Events (SSE).
    """
    async def event_generator():
        # Fetch Redis URL from DB dynamically
        from src.core.database.connection import get_db
        db = await get_db()
        settings = await db.system_settings.find_one({}) or {}
        redis_url = settings.get("redis_url", "redis://localhost:6379/0")
        
        # Establish connection for our subscriber
        r = aioredis.from_url(redis_url, decode_responses=True)
        pubsub = r.pubsub()
        channel_name = f"web_chat_{session_id}"
        await pubsub.subscribe(channel_name)
        
        try:
            # Yield an initial message to show connected
            yield {"event": "connected", "data": "connected"}
            
            # Listen indefinitely
            while True:
                if await request.is_disconnected():
                    break
                    
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    # Yield the text data back to the SSE client
                    yield {
                        "event": "message",
                        "data": json.dumps({"text": message['data']})
                    }
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
            await r.aclose()
            
    return EventSourceResponse(event_generator())
