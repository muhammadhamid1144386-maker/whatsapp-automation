from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from core.db import db, oid
from core.security import (audit, check_lockout, clear_login_attempts, create_access_token,
                           create_refresh_token, decode_token, get_current_user, hash_password,
                           rate_limit, record_failed_login, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str
    restaurant_name: str


def _set_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=43200, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=604800, path="/")


async def _session_payload(user: dict) -> dict:
    restaurant = await db.restaurants.find_one({"_id": oid(user["restaurant_id"])}) if user.get("restaurant_id") else None
    subscription = None
    if restaurant:
        sub = await db.subscriptions.find_one({"restaurant_id": str(restaurant["_id"])})
        if sub:
            subscription = {"status": sub.get("status"), "current_period_end": sub.get("current_period_end")}
    return {
        "id": str(user.get("_id") or user.get("id")),
        "email": user["email"],
        "name": user["name"],
        "role": user.get("role", "owner"),
        "platform_role": user.get("platform_role"),
        "restaurant_id": user.get("restaurant_id"),
        "subscription": subscription,
        "restaurant": {
            "id": str(restaurant["_id"]),
            "name": restaurant["name"],
            "slug": restaurant["slug"],
            "logo_url": restaurant.get("logo_url"),
            "city": restaurant.get("city"),
            "currency": restaurant.get("currency", "PKR"),
        } if restaurant else None,
    }


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response):
    email = body.email.lower()
    identifier = f"{request.client.host if request.client else 'unknown'}:{email}"
    rate_limit(f"login:{identifier}", 20, 60)
    await check_lockout(identifier)

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        await record_failed_login(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.get("platform_role") and user.get("restaurant_id"):
        sub = await db.subscriptions.find_one({"restaurant_id": user["restaurant_id"]}, {"status": 1})
        if sub and sub.get("status") == "blocked":
            await clear_login_attempts(identifier)
            raise HTTPException(
                status_code=403,
                detail="Your subscription is on hold because payment is pending. "
                       "Please complete your payment to restore access, or contact your account manager.",
            )

    await clear_login_attempts(identifier)
    user_id = str(user["_id"])
    access = create_access_token(user_id, email, user.get("restaurant_id") or "")
    refresh = create_refresh_token(user_id)
    _set_cookies(response, access, refresh)
    await audit(user.get("restaurant_id"), email, "login")
    payload = await _session_payload(user)
    return {**payload, "access_token": access}


@router.post("/register")
async def register(body: RegisterBody, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    now = datetime.now(timezone.utc)
    slug_base = body.restaurant_name.lower().replace(" ", "-")[:40]
    slug = slug_base
    suffix = 1
    while await db.restaurants.find_one({"slug": slug}):
        suffix += 1
        slug = f"{slug_base}-{suffix}"
    restaurant_result = await db.restaurants.insert_one(
        {"name": body.restaurant_name, "slug": slug, "currency": "PKR", "city": None, "demo": False, "created_at": now}
    )
    restaurant_id = str(restaurant_result.inserted_id)
    await db.restaurant_settings.insert_one(
        {"restaurant_id": restaurant_id,
         "opening_hours": [{"day": d, "open": "11:00", "close": "23:00", "closed": False} for d in range(7)],
         "delivery_areas": [], "delivery_fee": 150.0, "min_order": 500.0, "prep_time_min": 20,
         "prep_time_max": 30, "delivery_time_min": 15, "delivery_time_max": 20,
         "allow_orders_when_closed": False, "upsell_enabled": True, "ai_active": True, "timezone": "Asia/Karachi"}
    )
    user_result = await db.users.insert_one(
        {"email": email, "password_hash": hash_password(body.password), "name": body.name,
         "role": "owner", "restaurant_id": restaurant_id, "created_at": now}
    )
    user = await db.users.find_one({"_id": user_result.inserted_id})
    access = create_access_token(str(user_result.inserted_id), email, restaurant_id)
    refresh = create_refresh_token(str(user_result.inserted_id))
    _set_cookies(response, access, refresh)
    payload = await _session_payload(user)
    return {**payload, "access_token": access}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return await _session_payload(user)


@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token") or request.query_params.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_token(token, "refresh")
    user = await db.users.find_one({"_id": oid(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    access = create_access_token(str(user["_id"]), user["email"], user.get("restaurant_id") or "")
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=43200, path="/")
    return {"access_token": access}


@router.post("/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    await audit(user.get("restaurant_id"), user["email"], "logout")
    return {"ok": True}
