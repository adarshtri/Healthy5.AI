from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any
from src.core.database.connection import get_db
from src.core.models import SystemUser, Integration
from src.core.security import get_password_hash
from src.gateway.api.auth import get_current_user
from pydantic import BaseModel
import sys
import os

# Import webhook script logic safely
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
try:
    from scripts.set_webhook import set_webhook_for_token
except ImportError:
    # Fallback if scripts cannot be imported
    def set_webhook_for_token(token, name): pass

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"

class ProfileUpdate(BaseModel):
    profile_name: str

class IntegrationUpdate(BaseModel):
    name: str
    model_source: str
    allowed_agents: list[str] = ["general"]

@router.get("")
async def get_users(current_user: Any = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized. Admin only.")
    db = await get_db()
    users = await db.system_users.find().to_list(100)
    for u in users:
        u["_id"] = str(u["_id"])
        if "password_hash" in u:
            del u["password_hash"]
    return users

@router.post("/register")
async def create_user(user: UserCreate, current_user: Any = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized. Admin only.")
    
    db = await get_db()
    if await db.system_users.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already registered")
        
    new_user = SystemUser(
        username=user.username,
        password_hash=get_password_hash(user.password),
        role=user.role,
        integrations=[]
    )
    await db.system_users.insert_one(new_user.model_dump())
    return {"status": "success", "username": user.username}

@router.post("/integrations")
async def add_integration(integration: Integration, current_user: Any = Depends(get_current_user)):
    db = await get_db()
    
    integrations = current_user.get("integrations", [])
    found = False
    
    for i in range(len(integrations)):
        if integrations[i]["platform"] == integration.platform and integrations[i]["name"] == integration.name:
            integrations[i] = integration.model_dump()
            found = True
            break
            
    if not found:
        integrations.append(integration.model_dump())
        
    await db.system_users.update_one(
        {"username": current_user["username"]},
        {"$set": {"integrations": integrations}}
    )

    # Sync Webhook if it's Telegram
    if integration.platform == "telegram":
        display_name = current_user.get("profile_name") or current_user.get("username", "User")
        full_name = f"{display_name} - {integration.name}"
        set_webhook_for_token(integration.token, full_name)

    return {"status": "success", "integrations": integrations}

@router.delete("/integrations/{platform}/{token}")
async def remove_integration(
    platform: str, 
    token: str, 
    current_user: Any = Depends(get_current_user)
):
    db = await get_db()
    
    # Filter out the matching integration
    integrations = [
        intg for intg in current_user.get("integrations", [])
        if not (intg["platform"] == platform and intg["token"] == token)
    ]
    
    await db.system_users.update_one(
        {"username": current_user["username"]},
        {"$set": {"integrations": integrations}}
    )
    return {"status": "success", "integrations": integrations}

@router.put("/integrations/{platform}/{token}")
async def update_integration(
    platform: str, 
    token: str, 
    updates: IntegrationUpdate,
    current_user: Any = Depends(get_current_user)
):
    db = await get_db()
    
    integrations = current_user.get("integrations", [])
    updated = False
    
    for intg in integrations:
        if intg["platform"] == platform and intg["token"] == token:
            intg["name"] = updates.name
            intg["model_source"] = updates.model_source
            intg["allowed_agents"] = updates.allowed_agents
            updated = True
            break
            
    if not updated:
        raise HTTPException(status_code=404, detail="Integration not found")
        
    await db.system_users.update_one(
        {"username": current_user["username"]},
        {"$set": {"integrations": integrations}}
    )
    
    # If it's telegram, maybe we re-sync webhook with the new name
    if platform == "telegram":
        display_name = current_user.get("profile_name") or current_user.get("username", "User")
        full_name = f"{display_name} - {updates.name}"
        set_webhook_for_token(token, full_name)

    return {"status": "success", "integrations": integrations}

@router.post("/profile-name")
async def update_profile_name(update: ProfileUpdate, current_user: Any = Depends(get_current_user)):
    db = await get_db()
    await db.system_users.update_one(
        {"username": current_user["username"]},
        {"$set": {"profile_name": update.profile_name}}
    )
    return {"status": "success", "profile_name": update.profile_name}
