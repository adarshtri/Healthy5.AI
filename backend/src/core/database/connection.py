from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
CLIENT_NAME = "healthy5_ai"

client = AsyncIOMotorClient(MONGO_URL)
db = client[CLIENT_NAME]

async def get_db():
    return db
