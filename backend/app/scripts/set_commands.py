import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def set_commands():
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return
        
    url = f"https://api.telegram.org/bot{TOKEN}/setMyCommands"
    commands = [
        {"command": "chat", "description": "General Chat"},
        {"command": "weight", "description": "Weight Management"},
        {"command": "profile", "description": "Profile Management"},
        {"command": "remind", "description": "Set Reminders"}
    ]
    
    print("Registering commands with Telegram API...")
    response = requests.post(url, json={"commands": commands})
    
    if response.status_code == 200:
        print("✅ Menu commands successfully registered!")
    else:
        print(f"❌ Failed: {response.json()}")

if __name__ == "__main__":
    print(f"Using Token: {TOKEN[:5]}...")
    set_commands()
