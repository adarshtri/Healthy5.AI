from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel
from typing import Optional

from src.gateway.api.auth import get_current_user
from src.core.database import get_db
from src.core.models import SystemSettings
import requests
import os

router = APIRouter()

class SyncWebhookRequest(BaseModel):
    webhook_url: Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    telegram_webhook_url: Optional[str] = None
    journal_base_path: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_model: Optional[str] = None
    ollama_model: Optional[str] = None
    redis_url: Optional[str] = None
    secret_key: Optional[str] = None
    algorithm: Optional[str] = None
    telegram_bot_token: Optional[str] = None

@router.get("/settings", response_model=SystemSettings)
async def get_settings_endpoint(
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Admin access required."
        )
    db = await get_db()
    settings = await db.system_settings.find_one({})
    if not settings:
        return SystemSettings()
    return SystemSettings(**settings)

@router.post("/settings", response_model=SystemSettings)
async def update_settings_endpoint(
    request: SettingsUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Admin access required."
        )
    
    db = await get_db()
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    
    if not update_data:
        return await get_settings_endpoint(current_user)

    from datetime import datetime
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.system_settings.find_one_and_update(
        {},
        {"$set": update_data},
        upsert=True,
        return_document=True
    )
    return SystemSettings(**result)

def set_webhook_for_token(token: str, name: str, ngrok_url: str):
    """Registers the webhook for a specific bot token."""
    if not ngrok_url:
        print(f"⚠️ [{name}] Cannot set webhook: URL is missing.")
        return False
        
    url = f"https://api.telegram.org/bot{token}/setWebhook"
    webhook_url = f"{ngrok_url}/webhook/telegram/{token}"
    
    response = requests.post(url, data={"url": webhook_url})
    
    if response.status_code == 200:
        print(f"✅ [{name}] Webhook successfully set for ...{token[-5:]}")
        return True
    else:
        print(f"❌ [{name}] Failed to set webhook: {response.text}")
        return False

async def sync_all_webhooks(ngrok_url: str):
    logs = []
    logs.append(f"Server URL: {ngrok_url}")
    logs.append("-" * 30)
    
    tokens = []
    
    # 1. Primary Token from DB
    db = await get_db()
    settings = await db.system_settings.find_one({}) or {}
    main_token = settings.get("telegram_bot_token")
    if main_token:
        tokens.append((main_token, "Main Bot (System Settings)"))
    else:
        logs.append("Warning: Global fallback telegram_bot_token not found in system settings.")

    # 2. Fetch all unique tokens from MongoDB System Users
    
    try:
        users = db.system_users.find({"integrations": {"$not": {"$size": 0}}})
        async for user in users:
            for integration in user.get("integrations", []):
                # only sync telegram bots
                if integration.get("platform") == "telegram" and integration.get("token"):
                    token = integration["token"]
                    name = user.get("profile_name") or user.get("username", "User")
                    integration_name = integration.get("name", "")
                    
                    full_name = f"{name} - {integration_name}"
                    
                    if not any(token == t for t, _ in tokens):
                        tokens.append((token, f"Integration: {full_name}"))
    except Exception as e:
        logs.append(f"Could not fetch user tokens: {e}")
        
    logs.append(f"Found {len(tokens)} unique Bot Token(s) to register.\n")
    
    success_count = 0
    for token, name in tokens:
        if set_webhook_for_token(token, name, ngrok_url=ngrok_url):
            logs.append(f"✅ [{name}] Webhook successfully set for ...{token[-5:]}")
            success_count += 1
        else:
            logs.append(f"❌ [{name}] Failed to set webhook.")
            
    return {
        "success": True,
        "tokens_processed": len(tokens),
        "success_count": success_count,
        "logs": logs
    }

@router.post("/sync-webhooks")
async def sync_webhooks_endpoint(
    request: SyncWebhookRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Triggers a webhook sync across all registered Telegram bots (main + user integrations).
    Requires admin privileges.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Admin access required to sync webhooks."
        )

    try:
        url_to_use = request.webhook_url
        if not url_to_use:
            db = await get_db()
            settings = await db.system_settings.find_one({})
            if settings and settings.get("telegram_webhook_url"):
                url_to_use = settings["telegram_webhook_url"]
            else:
                raise HTTPException(status_code=400, detail="Webhook URL not provided and not found in settings.")

        # Import and run the refactored script logic
        result = await sync_all_webhooks(url_to_use)
        if result.get("success"):
            return {
                "message": "Webhook synchronization completed.",
                "details": result
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Webhook sync failed: {result.get('logs', [])}"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while syncing webhooks: {str(e)}"
        )
