from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class AgentSetupRequest(BaseModel):
    bot_token: str
    model_source: str
    agent_name: str = ""

@router.post("/agent")
async def setup_agent(request: AgentSetupRequest):
    """
    Endpoint to receive the agent setup details from the frontend.
    For this phase, we assume a single/default user.
    """
    logger.info(f"Received agent setup request for agent '{request.agent_name}' with source '{request.model_source}'")
    
    # In a real implementation with authentication, we would fetch the user_id from the session.
    # For now, we will update the default user profile (e.g., user_id=1) 
    # or just acknowledge the receipt if we haven't implemented the DB connection here yet.
    
    try:
        from src.core.database.connection import get_db
        db = await get_db()
        profiles_collection = db.profiles
        
        # We'll use a hardcoded default user_id for demonstration until auth is added
        DEFAULT_USER_ID = 1
        
        user = await profiles_collection.find_one({"user_id": DEFAULT_USER_ID})
        if not user:
            # Create a default user if it doesn't exist
            await profiles_collection.insert_one({
                "user_id": DEFAULT_USER_ID,
                "bot_token": request.bot_token,
                "model_source": request.model_source,
                "agent_name": request.agent_name,
                "active_agent": "general",
                "memories": [],
                "preferences": []
            })
            logger.info("Created new default user config")
        else:
            # Update existing default user
            await profiles_collection.update_one(
                {"user_id": DEFAULT_USER_ID},
                {"$set": {
                    "bot_token": request.bot_token,
                    "model_source": request.model_source,
                    "agent_name": request.agent_name
                }}
            )
            logger.info("Updated existing default user config")
            
        return {"status": "success", "message": "Agent configured successfully"}
        
    except Exception as e:
        logger.error(f"Failed to save agent configuration: {e}")
        # Even if DB fails, let's return success for the UI demo purpose 
        # (or handle properly depending on requirements)
        raise HTTPException(status_code=500, detail=str(e))
