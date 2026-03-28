from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import uuid4
from bcrypt import hashpw, gensalt, checkpw
from datetime import date, timedelta
import redis.asyncio as redis_mod
import json
import stripe

from .db.session import get_user_db, get_redis
from .models.user_models import User, User_Logs
from .schemas.user_schema import (
    UserCreated, CreateUser, UserLoginInput,
    CheckoutSessionRequest, CheckoutSessionResponse, UserProfileResponse,
)
from .core.config import settings, STRIPE_PRICE_MAP, PLAN_REQUEST_LIMITS
from .core.security import get_session_user
from .api.v1.api import api_router

stripe.api_key = settings.stripe_secret_key

app = FastAPI(title="DarkStone Stratum Vegetation Risk Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def api_health():
    return {"status": "ok"}


@app.post("/register", response_model=UserCreated, status_code=201)
async def register(user: CreateUser, db: AsyncSession = Depends(get_user_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already exists.")
    salt = gensalt()
    new_user = User(
        user_id=str(uuid4()),
        email=user.email,
        hashed_pwd=hashpw(user.password.encode(), salt).decode("utf-8"),
        organization_name=user.company_name,
        role=user.role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@app.post("/login")
async def login(
    credentials: UserLoginInput,
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_user_db),
):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if not checkpw(credentials.password.encode("utf-8"), user.hashed_pwd.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    session_id = str(uuid4())
    await cache.set(
        f"session: {session_id}",
        json.dumps({
            "user_id": user.user_id,
            "email": user.email,
            "is_active": user.is_active,
            "subscription_plan": user.subscription_plan,
        }),
        ex=86400,
    )
    return {"detail": "Logged in successfully.", "session_id": session_id}


@app.post("/logout")
async def logout(session_id: str, cache: redis_mod.Redis = Depends(get_redis)):
    await cache.delete(f"session: {session_id}")
    return {"detail": "Logged out successfully."}


@app.get("/me", response_model=UserProfileResponse)
async def get_profile(
    session_id: str,
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_user_db),
):
    user = await get_session_user(session_id, cache, db)
    return user


@app.post("/payments/create-checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    session_id: str,
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_user_db),
):
    user = await get_session_user(session_id, cache, db)
    price_id = STRIPE_PRICE_MAP.get(payload.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {payload.plan}")

    checkout = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        customer_email=user.email,
        metadata={"user_id": user.user_id, "plan": payload.plan},
        success_url="https://yourdomain.com/payment/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://yourdomain.com/payment/cancel",
        currency="inr",
    )
    return CheckoutSessionResponse(checkout_url=checkout.url)


@app.post("/payments/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_user_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"].get("user_id")
        plan = session["metadata"].get("plan")
        if user_id and plan:
            today = date.today()
            end_date = today + timedelta(days=30)
            await db.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(
                    subscription_plan=plan,
                    subscription_start=today,
                    subscription_end=end_date,
                    max_requests=PLAN_REQUEST_LIMITS.get(plan, 100),
                )
            )
            await db.commit()

    elif event["type"] in ("customer.subscription.deleted", "invoice.payment_failed"):
        sub = event["data"]["object"]
        customer_email = sub.get("customer_email") or sub.get("customer_details", {}).get("email")
        if customer_email:
            await db.execute(
                update(User)
                .where(User.email == customer_email)
                .values(
                    subscription_plan="Free",
                    max_requests=PLAN_REQUEST_LIMITS["Free"],
                    subscription_end=date.today(),
                )
            )
            await db.commit()

    return {"status": "ok"}