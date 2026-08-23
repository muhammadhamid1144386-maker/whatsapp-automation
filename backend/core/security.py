import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request

from core.db import db, oid

JWT_ALGORITHM = "HS256"
ACCESS_TTL_MINUTES = 60 * 12
REFRESH_TTL_DAYS = 7
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, restaurant_id: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "rid": restaurant_id,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TTL_MINUTES),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload


def _extract_token(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    token = request.cookies.get("access_token")
    if token:
        return token
    return request.query_params.get("token")


async def get_current_user(request: Request) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user = await db.users.find_one({"_id": oid(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user["id"] = str(user.pop("_id"))
    user.pop("password_hash", None)
    return user


async def tenant(user: dict = Depends(get_current_user)) -> str:
    """Returns the restaurant_id the authenticated user is allowed to touch."""
    restaurant_id = user.get("restaurant_id")
    if not restaurant_id:
        raise HTTPException(status_code=403, detail="User is not linked to a restaurant")
    return restaurant_id


async def record_failed_login(identifier: str) -> None:
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$inc": {"count": 1}, "$set": {"last_attempt": time.time()}},
        upsert=True,
    )


async def check_lockout(identifier: str) -> None:
    doc = await db.login_attempts.find_one({"identifier": identifier})
    if not doc:
        return
    if doc.get("count", 0) >= MAX_FAILED_ATTEMPTS:
        elapsed = time.time() - doc.get("last_attempt", 0)
        if elapsed < LOCKOUT_SECONDS:
            wait = int((LOCKOUT_SECONDS - elapsed) / 60) + 1
            raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {wait} minutes.")
        await db.login_attempts.delete_one({"identifier": identifier})


async def clear_login_attempts(identifier: str) -> None:
    await db.login_attempts.delete_one({"identifier": identifier})


async def audit(restaurant_id: Optional[str], actor: str, action: str, meta: Optional[dict] = None) -> None:
    await db.audit_logs.insert_one(
        {
            "restaurant_id": restaurant_id,
            "actor": actor,
            "action": action,
            "meta": meta or {},
            "created_at": datetime.now(timezone.utc),
        }
    )


_rate_buckets: dict[str, list[float]] = {}


def rate_limit(key: str, limit: int, window_seconds: int) -> None:
    now = time.time()
    hits = [t for t in _rate_buckets.get(key, []) if now - t < window_seconds]
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests, please slow down.")
    hits.append(now)
    _rate_buckets[key] = hits
