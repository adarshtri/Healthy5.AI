import asyncio
import sys
import os

# Ensure backend root is in PYTHONPATH so absolute imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.database.connection import get_db
from src.core.models import SystemUser
from src.core.security import get_password_hash

async def create_admin(username, password):
    db = await get_db()
    
    existing = await db.system_users.find_one({"username": username})
    if existing:
        print(f"User {username} already exists!")
        return
        
    admin_user = SystemUser(
        username=username,
        password_hash=get_password_hash(password),
        role="admin",
        integrations=[]
    )
    
    await db.system_users.insert_one(admin_user.model_dump())
    print(f"Admin user '{username}' created successfully!")
    
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python create_admin.py <username> <password>")
        sys.exit(1)
        
    u = sys.argv[1]
    p = sys.argv[2]
    asyncio.run(create_admin(u, p))
