"""Inbound message pipeline: idempotency -> persistence -> conversation state -> AI agent."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from pymongo.errors import DuplicateKeyError

from core.db import db, oid
from services import sheets
from services.agent import AgentContext, respond
from services.ai import detect_language
from services.orders import get_settings, is_open
from services.realtime import broker, customer_channel, dashboard_channel
from services.whatsapp import get_whatsapp_provider

logger = logging.getLogger(__name__)


async def _get_or_create_conversation(restaurant_id: str, phone: str) -> dict:
    conversation = await db.conversations.find_one({"restaurant_id": restaurant_id, "phone": phone})
    if conversation:
        return conversation
    customer = await db.customers.find_one({"restaurant_id": restaurant_id, "phone": phone})
    now = datetime.now(timezone.utc)
    doc = {
        "restaurant_id": restaurant_id,
        "customer_id": str(customer["_id"]) if customer else None,
        "phone": phone,
        "state": "GREETING",
        "language": "en",
        "ai_active": True,
        "last_message_at": now,
        "created_at": now,
    }
    result = await db.conversations.insert_one(dict(doc))
    doc["_id"] = result.inserted_id
    await broker.publish(dashboard_channel(restaurant_id), "NEW_CONVERSATION", {"conversation_id": str(result.inserted_id), "phone": phone})
    return doc


async def save_message(restaurant_id: str, conversation_id: str, sender: str, body: str, external_id: Optional[str] = None, message_type: str = "text") -> dict:
    doc = {
        "conversation_id": conversation_id,
        "restaurant_id": restaurant_id,
        "sender": sender,
        "body": body,
        "message_type": message_type,
        "external_id": external_id,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.messages.insert_one(dict(doc))
    doc["id"] = str(result.inserted_id)
    await broker.publish(
        dashboard_channel(restaurant_id), "NEW_MESSAGE",
        {"id": doc["id"], "conversation_id": conversation_id, "sender": sender, "body": body, "created_at": str(doc["created_at"])},
    )
    return doc


async def handle_incoming(restaurant: dict, phone: str, text: str, external_id: Optional[str] = None) -> dict:
    """Processes one inbound customer message. Safe to call twice with the same external_id."""
    restaurant_id = str(restaurant["_id"])
    external_id = external_id or f"auto:{uuid.uuid4().hex}"

    try:
        await db.processed_messages.insert_one(
            {"external_id": external_id, "restaurant_id": restaurant_id, "phone": phone, "created_at": datetime.now(timezone.utc)}
        )
    except DuplicateKeyError:
        logger.info("duplicate inbound message %s ignored", external_id)
        return {"duplicate": True, "replies": []}

    conversation = await _get_or_create_conversation(restaurant_id, phone)
    conversation_id = str(conversation["_id"])
    language = detect_language(text)

    await db.conversations.update_one(
        {"_id": conversation["_id"]},
        {"$set": {"language": language, "last_message_at": datetime.now(timezone.utc)}},
    )
    conversation["language"] = language

    inbound = await save_message(restaurant_id, conversation_id, "customer", text, external_id)
    await sheets.queue_sync(
        restaurant_id, "MESSAGE_CREATED", inbound["id"],
        {"conversation_id": conversation_id, "phone": phone, "sender": "customer", "body": text, "created_at": str(inbound["created_at"])},
    )

    if not conversation.get("ai_active", True):
        return {"duplicate": False, "replies": [], "handoff": True}

    settings = await get_settings(restaurant_id)
    customer = await db.customers.find_one({"restaurant_id": restaurant_id, "phone": phone})
    ctx = AgentContext(restaurant=restaurant, settings=settings, conversation=conversation, customer=customer, language=language)

    replies = await respond(ctx, text)
    provider = get_whatsapp_provider()
    for reply in replies:
        await db.messages.insert_one(
            {"conversation_id": conversation_id, "restaurant_id": restaurant_id, "sender": "ai",
             "body": reply, "message_type": "text", "external_id": None, "created_at": datetime.now(timezone.utc)}
        )
        await broker.publish(dashboard_channel(restaurant_id), "NEW_MESSAGE", {"conversation_id": conversation_id, "sender": "ai", "body": reply})
        await broker.publish(customer_channel(restaurant_id, phone), "WHATSAPP_MESSAGE", {"body": reply, "sender": "ai"})

    fresh = await db.conversations.find_one({"_id": conversation["_id"]})
    return {"duplicate": False, "replies": replies, "state": fresh.get("state"), "conversation_id": conversation_id, "language": language}


async def staff_reply(restaurant_id: str, conversation_id: str, text: str) -> dict:
    conversation = await db.conversations.find_one({"_id": oid(conversation_id), "restaurant_id": restaurant_id})
    if not conversation:
        return {"ok": False, "error": "Conversation not found"}
    await save_message(restaurant_id, conversation_id, "staff", text)
    await broker.publish(customer_channel(restaurant_id, conversation["phone"]), "WHATSAPP_MESSAGE", {"body": text, "sender": "staff"})
    return {"ok": True}
