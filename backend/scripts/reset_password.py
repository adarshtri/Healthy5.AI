import asyncio
import sys
import os

# Ensure backend root is in PYTHONPATH so absolute imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.database.connection import get_db
from src.core.models import SystemUser
from src.core.security import get_password_hash

async def reset_password(username, new_password):
    db = await get_db()
    
    existing = await db.system_users.find_one({"username": username})
    if not existing:
        print(f"User '{username}' does not exist!")
        return
        
    hashed_password = get_password_hash(new_password)
    
    await db.system_users.update_one(
        {"username": username},
        {"$set": {"password_hash": hashed_password}}
    )
    print(f"Password for user '{username}' has been successfully reset!")
    
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python reset_password.py <username> <new_password>")
        sys.exit(1)
        
    u = sys.argv[1]
    p = sys.argv[2]
    asyncio.run(reset_password(u, p))
