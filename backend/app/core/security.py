from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis_mod
import json

from ..core.config import settings
from ..db.session import get_user_db, get_redis
from ..models.user_models import User

bearer_scheme = HTTPBearer()

def decode_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_user_db),
) -> User:
    payload = decode_jwt(credentials.credentials)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject.")
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")
    return user

async def get_session_user(
    session_id: str,
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_user_db),
) -> User:
    data = await cache.get(f"session: {session_id}")
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid.")
    session = json.loads(data)
    result = await db.execute(select(User).where(User.user_id == session["user_id"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")
    return user

def require_active_quota(user: User) -> User:
    if user.max_requests != -1 and user.max_requests <= 0:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Request quota exhausted. Please upgrade your plan.")
    if user.subscription_end and user.subscription_end < datetime.now(timezone.utc).date():
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Subscription expired.")
    return user