import os
import requests
import asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

NGROK_URL = os.getenv("NGROK_URL")
if not NGROK_URL:
    print("Error: NGROK_URL not found in .env")
    exit(1)

def set_webhook_for_token(token: str, name: str):
    """Registers the webhook for a specific bot token."""
    url = f"https://api.telegram.org/bot{token}/setWebhook"
    webhook_url = f"{NGROK_URL}/webhook/telegram/{token}"
    
    response = requests.post(url, data={"url": webhook_url})
    
    if response.status_code == 200:
        print(f"✅ [{name}] Webhook successfully set for ...{token[-5:]}")
    else:
        print(f"❌ [{name}] Failed to set webhook: {response.text}")

async def main():
    print(f"Server URL: {NGROK_URL}")
    print("-" * 30)
    
    tokens = []
    
    # 1. Primary Token from .env
    main_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if main_token:
        tokens.append((main_token, "Main Bot (.env)"))
    else:
        print("Warning: TELEGRAM_BOT_TOKEN not found in .env")

    # 2. Fetch all unique tokens from MongoDB User Profiles
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    db = client["healthy5_ai"]
    
    try:
        profiles = db.profiles.find({"bot_token": {"$exists": True, "$ne": None}})
        async for profile in profiles:
            token = profile["bot_token"]
            name = profile.get("name", f"User {profile['user_id']}")
            
            # Avoid duplicate registrations if the main agent's token is in a profile
            if not any(token == t for t, _ in tokens):
                tokens.append((token, f"Profile: {name}"))
    except Exception as e:
        print(f"Could not connect to MongoDB to fetch user tokens: {e}")
        
    print(f"Found {len(tokens)} unique Bot Token(s) to register.\n")
    
    for token, name in tokens:
        set_webhook_for_token(token, name)
        
if __name__ == "__main__":
    asyncio.run(main())
