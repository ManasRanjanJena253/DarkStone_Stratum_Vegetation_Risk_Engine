from fastapi import FastAPI
from fastapi import Form, File, UploadFile, HTTPException
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_user_db, get_redis    # The top level folder is the /app folder according to the docker file, so imports look like this.
from app.models.user_models import User
from app.schemas.user_schema import UserCreated, CreateUser, UserLoginInput
from uuid import uuid4
from bcrypt import hashpw, gensalt, checkpw

import redis.asyncio as redis
import json
app = FastAPI()

# User apis
from sqlalchemy import select, insert, update
@app.get("/health")
def api_health():
    return {"Status": "OK"}

@app.post("/register", response_model = UserCreated)
async def register(user: CreateUser, db: AsyncSession = Depends(get_user_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    db_obj = result.scalar_one_or_none()    # Returns user obj or none.

    if db_obj:
        raise HTTPException(status_code = 400, detail = "This User Exists")
    salt = gensalt()
    new_user = User(
        user_id = str(uuid4()),
        email = user.email,
        hashed_pwd = hashpw(password = user.password.encode(), salt = salt).decode('utf-8')  # Storing using decode otherwise the using str() will also store the b" in the binary format which will break the checkpw.
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)  # Forces to push the changes to the db

    return new_user

@app.post("/login")
async def login(credentials: UserLoginInput, cache: redis.Redis = Depends(get_redis), db: AsyncSession = Depends(get_user_db)):
    check = await db.execute(select(User).where(User.email == credentials.email))
    user = check.scalar_one_or_none()
    if user :
        if checkpw(credentials.password.encode('utf-8'), user.hashed_pwd.encode('utf-8')):
            session_id = uuid4()
            session_details = {"user_id": user.user_id,
                               "email": user.email,
                               "is_active": user.is_active,
                               "subscription_plan": user.subscription_plan,
                               }
            await cache.set(f"session: {session_id}",
                            json.dumps(session_details),
                            ex = 86400)   # 'ex': Expiry time is seconds. Here the expiry is set to 1 day.
            return {"detail": "Logged in successfully.", "session_id": str(session_id)}

        else :
            raise HTTPException(status_code = 401)
    else :
        raise HTTPException(status_code = 404)

@app.post("/logout")
async def logout(session_id: str, cache: redis.Redis = Depends(get_redis)):
    await cache.delete(f"session:{session_id}")
    raise HTTPException(status_code = 200, detail = "Logged out Successfully.")

# @app.post("/enroll-User")
# async def enroll_user()