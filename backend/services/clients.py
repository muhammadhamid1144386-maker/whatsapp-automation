"""Provisioning a new platform client: restaurant + settings + owner login + subscription."""

import re
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException

from core.db import db
from core.security import hash_password
from services import subscriptions

WORDS = ("Spice", "Grill", "Tandoor", "Karahi", "Chaska", "Sizzle", "Dhaba", "Tikka")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug[:40] or "client"


def generate_password() -> str:
    """Readable but strong enough to hand over verbally."""
    word = secrets.choice(WORDS)
    digits = f"{secrets.randbelow(9000) + 1000}"
    tail = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
    return f"{word}-{digits}-{tail}"


async def unique_slug(name: str) -> str:
    base = slugify(name)
    slug = base
    suffix = 1
    while await db.restaurants.find_one({"slug": slug}):
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


async def provision(
    *,
    restaurant_name: str,
    owner_name: str,
    email: str | None,
    city: str | None,
    phone: str | None,
    whatsapp_number: str | None,
    amount: float,
    billing_period: str,
    created_by: str,
) -> dict:
    slug = await unique_slug(restaurant_name)
    login_email = (email or f"owner@{slug}.airestaurant.pk").strip().lower()
    if await db.users.find_one({"email": login_email}):
        raise HTTPException(status_code=400, detail=f"The login {login_email} is already taken. Pick another email.")

    password = generate_password()
    now = datetime.now(timezone.utc)

    restaurant_result = await db.restaurants.insert_one(
        {
            "name": restaurant_name,
            "slug": slug,
            "logo_url": None,
            "description": None,
            "phone": phone,
            "whatsapp_number": whatsapp_number,
            "address": None,
            "city": city,
            "currency": "PKR",
            "ai_greeting": f"Assalam o Alaikum! {restaurant_name} mein khush aamdeed. Aap kya order karna chahenge?",
            "business_rules": None,
            "demo": False,
            "created_at": now,
        }
    )
    restaurant_id = str(restaurant_result.inserted_id)

    await db.restaurant_settings.insert_one(
        {
            "restaurant_id": restaurant_id,
            "opening_hours": [{"day": d, "open": "11:00", "close": "23:00", "closed": False} for d in range(7)],
            "delivery_areas": [],
            "delivery_fee": 150.0,
            "min_order": 500.0,
            "prep_time_min": 20,
            "prep_time_max": 30,
            "delivery_time_min": 15,
            "delivery_time_max": 20,
            "allow_orders_when_closed": False,
            "upsell_enabled": True,
            "ai_active": True,
            "timezone": "Asia/Karachi",
        }
    )
    await db.whatsapp_sessions.insert_one(
        {"restaurant_id": restaurant_id, "provider": "simulator", "status": "disconnected",
         "connected_number": None, "qr_payload": None, "last_connected_at": None, "updated_at": now}
    )
    await db.google_sheet_connections.insert_one(
        {"restaurant_id": restaurant_id, "status": "not_connected", "spreadsheet_id": None,
         "spreadsheet_name": None, "service_account_email": None, "last_sync_at": None,
         "last_error": None, "updated_at": now}
    )
    await db.users.insert_one(
        {
            "email": login_email,
            "password_hash": hash_password(password),
            "name": owner_name or restaurant_name,
            "role": "owner",
            "platform_role": None,
            "restaurant_id": restaurant_id,
            "created_at": now,
        }
    )
    # Handover credentials, readable only by the platform admin who created the client.
    await db.client_credentials.insert_one(
        {
            "restaurant_id": restaurant_id,
            "email": login_email,
            "password": password,
            "issued_at": now,
            "issued_by": created_by,
        }
    )
    await subscriptions.get_or_create(restaurant_id, amount=amount, period=billing_period)
    sub = await subscriptions.update_plan(restaurant_id, amount=amount, billing_period=billing_period)
    await subscriptions.alert(
        restaurant_id, restaurant_name, "client_created", "info",
        f"New client {restaurant_name} onboarded. First payment of PKR {float(amount or 0):,.0f} due {sub['current_period_end'].date() if hasattr(sub['current_period_end'], 'date') else sub['current_period_end']}.",
    )

    return {"restaurant_id": restaurant_id, "slug": slug, "email": login_email, "password": password, "subscription": sub}


async def regenerate_password(restaurant_id: str, actor: str) -> dict:
    user = await db.users.find_one({"restaurant_id": restaurant_id, "platform_role": None})
    if not user:
        user = await db.users.find_one({"restaurant_id": restaurant_id})
    if not user:
        raise HTTPException(status_code=404, detail="This client has no owner login yet")
    password = generate_password()
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(password)}})
    await db.client_credentials.update_one(
        {"restaurant_id": restaurant_id},
        {"$set": {"email": user["email"], "password": password,
                  "issued_at": datetime.now(timezone.utc), "issued_by": actor}},
        upsert=True,
    )
    await db.login_attempts.delete_many({"identifier": {"$regex": re.escape(user["email"])}})
    return {"email": user["email"], "password": password}
