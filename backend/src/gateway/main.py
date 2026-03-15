from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Note: We commented out the scheduler here temporarily until Phase 3/4
# from src.workers.scheduler import start_scheduler

from src.gateway.api.setup import router as setup_router
from src.gateway.api.auth import router as auth_router
from src.gateway.api.users import router as users_router
from src.gateway.api.chat import router as chat_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize global broker with our DB settings so workers/UI use correct Redis
    from src.core.database.connection import get_db
    from src.events.broker import _init_redis
    db = await get_db()
    settings = await db.system_settings.find_one({}) or {}
    redis_url = settings.get("redis_url", "redis://localhost:6379/0")
    
    _init_redis(redis_url)
    
    # Configure the RQ Dashboard flask app with this async-loaded URL
    flask_app.config["RQ_DASHBOARD_REDIS_URL"] = (redis_url,)
    
    # start_scheduler()
    yield
    # Shutdown

from fastapi.middleware.wsgi import WSGIMiddleware
from flask import Flask
import rq_dashboard
import os

app = FastAPI(title="Healthy5.AI Backend", lifespan=lifespan)

# Build a mini Flask app for RQ Dashboard
flask_app = Flask(__name__)
flask_app.config.from_object(rq_dashboard.default_settings)
flask_app.config["RQ_DASHBOARD_REDIS_URL"] = ("redis://localhost:6379/0",) # Default overridden in lifespan
flask_app.register_blueprint(rq_dashboard.blueprint, url_prefix="")

# Mount RQ Dashboard
app.mount("/admin/rq", WSGIMiddleware(flask_app))

# Add CORS Middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Allowed dev origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(setup_router, prefix="/api/setup", tags=["setup"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])

from src.gateway.api.admin import router as admin_router
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

@app.get("/")
async def root():
    return {"message": "Healthy5.AI API is running"}

@app.post("/webhook/telegram/{token}")
async def telegram_webhook(token: str, request: Request):
    """
    Endpoint to receive updates from Telegram.
    The URL dynamically accepts the Bot Token to route multiple bots to the same backend.
    """
    try:
        data = await request.json()
        
        # We need to extract the basic identifier (chat_id) from the raw Telegram JSON
        # A standard telegram message usually has 'message' -> 'chat' -> 'id'
        chat_id = "unknown"
        text_content = None
        if "message" in data:
            chat_id = str(data["message"].get("chat", {}).get("id", "unknown"))
            text_content = data["message"].get("text", "")
            
        # 1. Normalize the event
        from src.events.schemas import ReceivedMessage
        event = ReceivedMessage(
            source_platform="telegram",
            source_id=chat_id,
            bot_token_or_id=token,
            text_content=text_content,
            raw_payload=data
        )
        
        # 2. Push to the Message Bus (Redis Queue)
        from src.events.broker import get_incoming_queue
        queue = get_incoming_queue()
        queue.enqueue("src.workers.agent_worker.process_incoming", event.model_dump())
        
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook normalization error: {e}")
        return {"status": "error"}
