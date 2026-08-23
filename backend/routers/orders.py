from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.db import db, oid
from core.security import audit, get_current_user, tenant
from models import Order, OrderStatusHistory
from services import orders as order_service
from services import sheets

router = APIRouter(prefix="/api/orders", tags=["orders"])


class StatusBody(BaseModel):
    status: str
    reason: Optional[str] = None


@router.get("")
async def list_orders(
    restaurant_id: str = Depends(tenant),
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, le=300),
):
    query: dict = {"restaurant_id": restaurant_id}
    if status and status != "ALL":
        query["status"] = status.upper()
    if search:
        query["$or"] = [
            {"order_number": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"customer_phone": {"$regex": search, "$options": "i"}},
        ]
    docs = await db.orders.find(query).sort("created_at", -1).to_list(limit)
    return [Order.from_mongo(d).model_dump() for d in docs]


@router.get("/{order_id}")
async def get_order(order_id: str, restaurant_id: str = Depends(tenant)):
    order = await db.orders.find_one({"_id": oid(order_id), "restaurant_id": restaurant_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    history = await db.order_status_history.find({"order_id": order_id}).sort("created_at", 1).to_list(50)
    conversation = None
    if order.get("conversation_id"):
        conversation = await db.conversations.find_one({"_id": oid(order["conversation_id"])})
    customer_orders = await db.orders.count_documents({"restaurant_id": restaurant_id, "customer_id": order.get("customer_id")}) if order.get("customer_id") else 0
    jobs = await db.google_sync_jobs.find({"entity_id": order_id}).sort("created_at", -1).to_list(10)
    return {
        "order": Order.from_mongo(order).model_dump(),
        "history": [OrderStatusHistory.from_mongo(h).model_dump() for h in history],
        "conversation_id": order.get("conversation_id"),
        "conversation_phone": (conversation or {}).get("phone"),
        "customer_order_count": customer_orders,
        "sync_jobs": [
            {"event": j["event"], "sync_status": j["sync_status"], "sync_attempts": j.get("sync_attempts", 0),
             "error_message": j.get("error_message"), "last_attempt": j.get("last_attempt")}
            for j in jobs
        ],
    }


@router.post("/{order_id}/status")
async def set_status(order_id: str, body: StatusBody, restaurant_id: str = Depends(tenant), user: dict = Depends(get_current_user)):
    result = await order_service.change_status(restaurant_id, order_id, body.status, changed_by=user["email"], reason=body.reason)
    await audit(restaurant_id, user["email"], "order.status", {"order_id": order_id, "status": body.status})
    return result


@router.post("/{order_id}/resync")
async def resync(order_id: str, restaurant_id: str = Depends(tenant)):
    order = await db.orders.find_one({"_id": oid(order_id), "restaurant_id": restaurant_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
    await sheets.queue_sync(
        restaurant_id, "ORDER_UPDATED", order_id,
        {"order_number": order["order_number"], "restaurant_name": (restaurant or {}).get("name", ""),
         "customer_name": order["customer_name"], "customer_phone": order["customer_phone"],
         "order_type": order["order_type"], "items_text": order_service.items_text(order["items"]),
         "subtotal": order["subtotal"], "delivery_fee": order["delivery_fee"], "discount": order.get("discount", 0),
         "total": order["total"], "address": order.get("address") or "", "payment_method": order.get("payment_method", "Cash"),
         "status": order["status"], "created_at": str(order["created_at"]), "updated_at": str(order["updated_at"])},
    )
    return await sheets.drain(restaurant_id, limit=10)
