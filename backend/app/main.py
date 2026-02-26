from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import Update
from .bot import dp
from .scheduler import start_scheduler

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown

app = FastAPI(title="Healthy5.AI Backend", lifespan=lifespan)

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
        # 1. Instantiate an ephemeral Bot using the token from the URL
        bot = Bot(token=token)
        
        # 2. Parse the incoming JSON into an Aiogram Update object
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        
        # 3. Feed the update to the shared dispatcher logic
        await dp.feed_update(bot, update)
        
        # 4. Cleanup session
        await bot.session.close()
        
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error"}
