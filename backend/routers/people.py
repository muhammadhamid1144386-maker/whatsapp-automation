from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.db import db, oid
from core.security import tenant
from models import Conversation, Customer, Message, Order
from services.processor import staff_reply

router = APIRouter(prefix="/api", tags=["people"])


class ReplyBody(BaseModel):
    body: str


class HandoffBody(BaseModel):
    ai_active: bool


@router.get("/customers")
async def list_customers(restaurant_id: str = Depends(tenant), search: Optional[str] = None, limit: int = Query(200, le=500)):
    query: dict = {"restaurant_id": restaurant_id}
    if search:
        query["$or"] = [{"name": {"$regex": search, "$options": "i"}}, {"phone": {"$regex": search, "$options": "i"}}]
    docs = await db.customers.find(query).sort("total_spent", -1).to_list(limit)
    return [Customer.from_mongo(d).model_dump() for d in docs]


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: str, restaurant_id: str = Depends(tenant)):
    customer = await db.customers.find_one({"_id": oid(customer_id), "restaurant_id": restaurant_id})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    orders = await db.orders.find({"restaurant_id": restaurant_id, "customer_id": customer_id}).sort("created_at", -1).to_list(50)
    conversation = await db.conversations.find_one({"restaurant_id": restaurant_id, "phone": customer["phone"]})
    return {
        "customer": Customer.from_mongo(customer).model_dump(),
        "orders": [Order.from_mongo(o).model_dump() for o in orders],
        "conversation_id": str(conversation["_id"]) if conversation else None,
    }


@router.get("/conversations")
async def list_conversations(restaurant_id: str = Depends(tenant), limit: int = Query(100, le=300)):
    docs = await db.conversations.find({"restaurant_id": restaurant_id}).sort("last_message_at", -1).to_list(limit)
    out = []
    for doc in docs:
        conversation_id = str(doc["_id"])
        last = await db.messages.find({"conversation_id": conversation_id}).sort("created_at", -1).to_list(1)
        customer = await db.customers.find_one({"restaurant_id": restaurant_id, "phone": doc["phone"]})
        out.append({
            **Conversation.from_mongo(doc).model_dump(),
            "customer_name": (customer or {}).get("name"),
            "message_count": await db.messages.count_documents({"conversation_id": conversation_id}),
            "last_message": last[0]["body"] if last else None,
            "last_sender": last[0]["sender"] if last else None,
        })
    return out


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, restaurant_id: str = Depends(tenant)):
    conversation = await db.conversations.find_one({"_id": oid(conversation_id), "restaurant_id": restaurant_id})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await db.messages.find({"conversation_id": conversation_id}).sort("created_at", 1).to_list(500)
    customer = await db.customers.find_one({"restaurant_id": restaurant_id, "phone": conversation["phone"]})
    orders = await db.orders.find({"restaurant_id": restaurant_id, "conversation_id": conversation_id}).sort("created_at", -1).to_list(20)
    return {
        "conversation": Conversation.from_mongo(conversation).model_dump(),
        "customer": Customer.from_mongo(customer).model_dump() if customer else None,
        "messages": [Message.from_mongo(m).model_dump() for m in messages],
        "orders": [Order.from_mongo(o).model_dump() for o in orders],
    }


@router.post("/conversations/{conversation_id}/handoff")
async def toggle_handoff(conversation_id: str, body: HandoffBody, restaurant_id: str = Depends(tenant)):
    result = await db.conversations.update_one(
        {"_id": oid(conversation_id), "restaurant_id": restaurant_id},
        {"$set": {"ai_active": body.ai_active, "state": "HUMAN_HANDOFF" if not body.ai_active else "SELECTING_ITEMS"}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True, "ai_active": body.ai_active}


@router.post("/conversations/{conversation_id}/reply")
async def reply(conversation_id: str, body: ReplyBody, restaurant_id: str = Depends(tenant)):
    result = await staff_reply(restaurant_id, conversation_id, body.body)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result
