from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from src.core.database.connection import get_db
from src.core.security import verify_password, create_access_token
from typing import Any
from jose import jwt, JWTError
import os

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Any:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        db = await get_db()
        settings = await db.system_settings.find_one({}) or {}
        secret_key = settings.get("secret_key", "default-secret-key-please-change-in-production")
        algorithm = settings.get("algorithm", "HS256")
        
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    db = await get_db()
    user_dict = await db.system_users.find_one({"username": username})
    if user_dict is None:
        raise credentials_exception
    return user_dict

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = await get_db()
    user_dict = await db.system_users.find_one({"username": form_data.username})
    
    if not user_dict or not verify_password(form_data.password, user_dict["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    settings = await db.system_settings.find_one({}) or {}
    secret_key = settings.get("secret_key", "default-secret-key-please-change-in-production")
    algorithm = settings.get("algorithm", "HS256")
        
    access_token = create_access_token(data={"sub": user_dict["username"]}, secret_key=secret_key, algorithm=algorithm)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: Any = Depends(get_current_user)):
    user = dict(current_user)
    if "_id" in user:
        user["_id"] = str(user["_id"])
    if "password_hash" in user:
        del user["password_hash"]
    return user
