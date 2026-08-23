"""Public customer-facing chat endpoint used by the WhatsApp simulator."""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.db import db, oid
from core.security import rate_limit
from models import Message
from services.orders import get_settings, is_open
from services.processor import handle_incoming

router = APIRouter(prefix="/api/chat", tags=["chat"])


class InboundBody(BaseModel):
    phone: str = Field(min_length=5, max_length=25)
    text: str = Field(min_length=1, max_length=1200)
    client_message_id: Optional[str] = None


@router.get("/{slug}")
async def restaurant_public(slug: str):
    restaurant = await db.restaurants.find_one({"slug": slug})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    restaurant_id = str(restaurant["_id"])
    settings = await get_settings(restaurant_id)
    open_now, opens_at = is_open(settings)
    session = await db.whatsapp_sessions.find_one({"restaurant_id": restaurant_id})
    return {
        "name": restaurant["name"],
        "slug": restaurant["slug"],
        "logo_url": restaurant.get("logo_url"),
        "city": restaurant.get("city"),
        "whatsapp_number": restaurant.get("whatsapp_number"),
        "ai_greeting": restaurant.get("ai_greeting"),
        "open_now": open_now,
        "opens_at": opens_at,
        "channel_status": (session or {}).get("status", "disconnected"),
    }


@router.get("/{slug}/history")
async def history(slug: str, phone: str):
    restaurant = await db.restaurants.find_one({"slug": slug})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    conversation = await db.conversations.find_one({"restaurant_id": str(restaurant["_id"]), "phone": phone})
    if not conversation:
        return {"conversation_id": None, "messages": [], "ai_active": True}
    messages = await db.messages.find({"conversation_id": str(conversation["_id"])}).sort("created_at", 1).to_list(300)
    return {
        "conversation_id": str(conversation["_id"]),
        "ai_active": conversation.get("ai_active", True),
        "state": conversation.get("state"),
        "messages": [Message.from_mongo(m).model_dump() for m in messages],
    }


@router.post("/{slug}/message")
async def inbound(slug: str, body: InboundBody, request: Request):
    rate_limit(f"chat:{slug}:{body.phone}", 30, 60)
    restaurant = await db.restaurants.find_one({"slug": slug})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    external_id = f"sim:{slug}:{body.phone}:{body.client_message_id or uuid.uuid4().hex}"
    result = await handle_incoming(restaurant, body.phone, body.text.strip(), external_id)
    return result


@router.post("/{slug}/reset")
async def reset(slug: str, phone: str):
    """Clears a simulator conversation so the demo can be replayed from scratch."""
    restaurant = await db.restaurants.find_one({"slug": slug})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    restaurant_id = str(restaurant["_id"])
    conversation = await db.conversations.find_one({"restaurant_id": restaurant_id, "phone": phone})
    if conversation:
        conversation_id = str(conversation["_id"])
        await db.messages.delete_many({"conversation_id": conversation_id})
        await db.carts.delete_many({"conversation_id": conversation_id})
        await db.conversations.delete_one({"_id": oid(conversation_id)})
    return {"ok": True}
