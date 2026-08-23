"""Order pricing, creation and lifecycle. All money is computed here, never by the LLM."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core.db import db, next_sequence, oid
from models import STATUS_EVENT, OrderStatus, SyncStatus
from services import cart as cart_service
from services import sheets
from services.notifications import notifications, order_placed_text, status_text
from services.realtime import broker, customer_channel, dashboard_channel

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS = {
    OrderStatus.NEW.value: {OrderStatus.CONFIRMED.value, OrderStatus.REJECTED.value, OrderStatus.CANCELLED.value},
    OrderStatus.CONFIRMED.value: {OrderStatus.PREPARING.value, OrderStatus.CANCELLED.value},
    OrderStatus.PREPARING.value: {OrderStatus.READY.value, OrderStatus.CANCELLED.value},
    OrderStatus.READY.value: {OrderStatus.OUT_FOR_DELIVERY.value, OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value},
    OrderStatus.OUT_FOR_DELIVERY.value: {OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value},
    OrderStatus.DELIVERED.value: set(),
    OrderStatus.REJECTED.value: set(),
    OrderStatus.CANCELLED.value: set(),
}


async def get_settings(restaurant_id: str) -> dict:
    settings = await db.restaurant_settings.find_one({"restaurant_id": restaurant_id})
    return settings or {}


def eta_for(settings: dict, order_type: str) -> tuple[int, int]:
    prep_min = int(settings.get("prep_time_min", 20))
    prep_max = int(settings.get("prep_time_max", 30))
    if order_type == "delivery":
        return prep_min + int(settings.get("delivery_time_min", 15)), prep_max + int(settings.get("delivery_time_max", 20))
    return prep_min, prep_max


def _parse_hhmm(value, default: int) -> int:
    try:
        hour, minute = [int(part) for part in str(value).split(":")[:2]]
        return hour * 60 + minute
    except (ValueError, AttributeError):
        return default


def _next_opening(hours: list[dict], weekday: int) -> str:
    for step in range(1, 8):
        day = (weekday + step) % 7
        entry = next((h for h in hours if int(h.get("day", 0)) == day), None)
        if entry and not entry.get("closed"):
            return entry.get("open", "11:00")
    return ""


def is_open(settings: dict, now: Optional[datetime] = None) -> tuple[bool, str]:
    """Returns (open_now, next_opening_time). Handles windows that run past midnight."""
    hours = settings.get("opening_hours") or []
    if not hours:
        return True, ""
    now = now or datetime.now(timezone.utc)
    local = now + timedelta(hours=5)  # Asia/Karachi is UTC+5 with no DST
    weekday = local.weekday()
    minutes_now = local.hour * 60 + local.minute

    yesterday = next((h for h in hours if int(h.get("day", 0)) == (weekday - 1) % 7), None)
    if yesterday and not yesterday.get("closed"):
        opens = _parse_hhmm(yesterday.get("open"), 660)
        closes = _parse_hhmm(yesterday.get("close"), 1410)
        if closes <= opens and minutes_now < closes:
            return True, ""

    today = next((h for h in hours if int(h.get("day", 0)) == weekday), None)
    if not today or today.get("closed"):
        return False, _next_opening(hours, weekday)

    opens = _parse_hhmm(today.get("open"), 660)
    closes = _parse_hhmm(today.get("close"), 1410)
    if closes <= opens:
        if minutes_now >= opens:
            return True, ""
    elif opens <= minutes_now <= closes:
        return True, ""

    if minutes_now < opens:
        return False, today.get("open", "11:00")
    return False, _next_opening(hours, weekday)


async def calculate_totals(restaurant_id: str, items: list[dict], order_type: Optional[str]) -> dict:
    settings = await get_settings(restaurant_id)
    subtotal = 0.0
    for line in items:
        subtotal += float(line["unit_price"]) * int(line["quantity"])
    delivery_fee = float(settings.get("delivery_fee", 150)) if order_type == "delivery" else 0.0
    discount = 0.0
    total = subtotal + delivery_fee - discount
    eta_min, eta_max = eta_for(settings, order_type or "pickup")
    return {
        "subtotal": round(subtotal, 2),
        "delivery_fee": round(delivery_fee, 2),
        "discount": round(discount, 2),
        "total": round(total, 2),
        "currency": "PKR",
        "min_order": float(settings.get("min_order", 0)),
        "eta_min": eta_min,
        "eta_max": eta_max,
    }


def items_text(items: list[dict]) -> str:
    return ", ".join(f"{i['quantity']}x {i['name']}" for i in items)


async def _queue_order_sync(restaurant: dict, order: dict) -> None:
    payload = {
        "order_number": order["order_number"],
        "restaurant_name": restaurant.get("name", ""),
        "customer_name": order["customer_name"],
        "customer_phone": order["customer_phone"],
        "order_type": order["order_type"],
        "items_text": items_text(order["items"]),
        "subtotal": order["subtotal"],
        "delivery_fee": order["delivery_fee"],
        "discount": order["discount"],
        "total": order["total"],
        "address": order.get("address") or "",
        "payment_method": order.get("payment_method", "Cash"),
        "status": order["status"],
        "created_at": str(order["created_at"]),
        "updated_at": str(order["updated_at"]),
    }
    await sheets.queue_sync(str(restaurant["_id"]), "ORDER_CREATED", order["id"], payload)
    await sheets.queue_sync(
        str(restaurant["_id"]), "ORDER_ITEMS", order["id"],
        {"order_number": order["order_number"], "items": order["items"]},
    )


async def create_order(
    restaurant_id: str,
    conversation_id: Optional[str],
    *,
    source: str = "whatsapp",
    language: str = "en",
) -> dict:
    """Creates an order from the server-side cart. Idempotent per cart."""
    restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    settings = await get_settings(restaurant_id)

    cart = await cart_service.get_cart(restaurant_id, conversation_id)
    lines = cart.get("items", [])
    if not lines:
        return {"ok": False, "error": "Cart is empty. Add items before creating the order."}
    if not cart.get("order_type"):
        return {"ok": False, "error": "Ask the customer whether they want delivery or pickup, then call set_order_details."}
    if not cart.get("customer_name"):
        return {"ok": False, "error": "Customer name is missing. Ask for it and call set_order_details."}
    if cart["order_type"] == "delivery" and not cart.get("address"):
        return {"ok": False, "error": "Delivery address is missing. Ask for it and call set_order_details."}

    open_now, opens_at = is_open(settings)
    if not open_now and not settings.get("allow_orders_when_closed", False):
        return {"ok": False, "error": f"The restaurant is currently closed. It opens at {opens_at}. Do not place the order."}

    # Re-validate every item against the live menu and snapshot prices.
    snapshot: list[dict] = []
    for line in lines:
        item = await db.menu_items.find_one({"_id": oid(line["item_id"]), "restaurant_id": restaurant_id})
        if not item:
            return {"ok": False, "error": f"{line['name']} is no longer on the menu."}
        if not item.get("available", True):
            return {"ok": False, "error": f"{item['name']} just went out of stock. Please remove it."}
        qty = int(line["quantity"])
        unit = float(item["price"])
        snapshot.append(
            {"item_id": str(item["_id"]), "name": item["name"], "unit_price": unit, "quantity": qty, "line_total": round(unit * qty, 2)}
        )

    totals = await calculate_totals(restaurant_id, snapshot, cart["order_type"])
    if totals["subtotal"] < totals["min_order"]:
        return {"ok": False, "error": f"Minimum order is PKR {totals['min_order']:.0f}. Current subtotal is PKR {totals['subtotal']:.0f}."}

    phone = cart.get("customer_phone")
    conversation = await db.conversations.find_one({"_id": oid(conversation_id)}) if conversation_id else None
    if not phone and conversation:
        phone = conversation.get("phone")

    customer = await _upsert_customer(restaurant_id, phone, cart.get("customer_name"))
    order_number = f"ORD-{await next_sequence(f'order:{restaurant_id}', 1000)}"
    now = datetime.now(timezone.utc)
    idempotency_key = f"{conversation_id or 'manual'}:{str(cart['_id'])}:{len(snapshot)}:{totals['total']}"

    doc = {
        "restaurant_id": restaurant_id,
        "order_number": order_number,
        "conversation_id": conversation_id,
        "customer_id": str(customer["_id"]) if customer else None,
        "customer_name": cart.get("customer_name"),
        "customer_phone": phone,
        "order_type": cart["order_type"],
        "items": snapshot,
        "subtotal": totals["subtotal"],
        "delivery_fee": totals["delivery_fee"],
        "discount": totals["discount"],
        "total": totals["total"],
        "address": cart.get("address"),
        "payment_method": cart.get("payment_method", "Cash"),
        "status": OrderStatus.NEW.value,
        "eta_min": totals["eta_min"],
        "eta_max": totals["eta_max"],
        "language": language,
        "reject_reason": None,
        "google_sync_status": SyncStatus.PENDING.value,
        "google_synced_at": None,
        "idempotency_key": idempotency_key,
        "source": source,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await db.orders.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.orders.find_one({"idempotency_key": idempotency_key})
        return {"ok": True, "duplicate": True, "order_number": existing["order_number"], "total": existing["total"]}

    order_id = str(result.inserted_id)
    doc["id"] = order_id

    await db.order_items.insert_many(
        [{"order_id": order_id, "restaurant_id": restaurant_id, **line} for line in snapshot]
    )
    await db.order_status_history.insert_one(
        {"order_id": order_id, "restaurant_id": restaurant_id, "old_status": None,
         "new_status": OrderStatus.NEW.value, "changed_by": "customer", "note": "Order placed via WhatsApp", "created_at": now}
    )
    await _bump_customer_stats(restaurant_id, customer, totals["total"], now)

    payload = _order_event_payload(doc)
    await broker.publish(dashboard_channel(restaurant_id), "NEW_ORDER", payload)

    text = order_placed_text(doc, restaurant, language)
    await notifications.notify_customer(restaurant_id, phone, text)

    await _queue_order_sync(restaurant, doc)
    if customer:
        await sheets.queue_sync(
            restaurant_id, "CUSTOMER_UPDATED", str(customer["_id"]),
            {"customer_id": str(customer["_id"]), "name": cart.get("customer_name"), "phone": phone,
             "total_orders": customer.get("total_orders", 0) + 1,
             "total_spent": customer.get("total_spent", 0) + totals["total"],
             "last_order": str(now), "created_at": str(customer.get("created_at", now))},
        )

    await cart_service.clear(conversation_id)
    if conversation_id:
        await db.conversations.update_one({"_id": oid(conversation_id)}, {"$set": {"state": "ORDER_PLACED"}})

    return {
        "ok": True,
        "order_number": order_number,
        "order_id": order_id,
        "status": OrderStatus.NEW.value,
        "subtotal": totals["subtotal"],
        "delivery_fee": totals["delivery_fee"],
        "total": totals["total"],
        "eta_min": totals["eta_min"],
        "eta_max": totals["eta_max"],
        "order_type": cart["order_type"],
        "confirmation_sent": True,
    }


async def change_status(
    restaurant_id: str, order_id: str, new_status: str, changed_by: str = "staff", reason: Optional[str] = None
) -> dict:
    order = await db.orders.find_one({"_id": oid(order_id), "restaurant_id": restaurant_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    new_status = new_status.upper()
    if new_status not in STATUS_EVENT:
        raise HTTPException(status_code=400, detail="Unknown status")
    old_status = order["status"]
    if new_status == old_status:
        raise HTTPException(status_code=400, detail=f"Order is already {old_status}")
    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise HTTPException(status_code=400, detail=f"Cannot move an order from {old_status} to {new_status}")
    if new_status == OrderStatus.OUT_FOR_DELIVERY.value and order["order_type"] != "delivery":
        raise HTTPException(status_code=400, detail="Pickup orders cannot go out for delivery")

    now = datetime.now(timezone.utc)
    updates = {"status": new_status, "updated_at": now}
    if reason:
        updates["reject_reason"] = reason
    await db.orders.update_one({"_id": oid(order_id)}, {"$set": updates})
    await db.order_status_history.insert_one(
        {"order_id": order_id, "restaurant_id": restaurant_id, "old_status": old_status,
         "new_status": new_status, "changed_by": changed_by, "note": reason, "created_at": now}
    )
    order.update(updates)
    order["id"] = order_id

    restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
    await broker.publish(dashboard_channel(restaurant_id), STATUS_EVENT[OrderStatus(new_status)], _order_event_payload(order))

    text = status_text(order, restaurant or {}, new_status, order.get("language", "en"), reason)
    if text and order.get("customer_phone"):
        await notifications.notify_customer(restaurant_id, order["customer_phone"], text)
        await broker.publish(
            customer_channel(restaurant_id, order["customer_phone"]),
            "ORDER_STATUS",
            {"order_number": order["order_number"], "status": new_status},
        )

    await db.orders.update_one({"_id": oid(order_id)}, {"$set": {"google_sync_status": SyncStatus.PENDING.value}})
    await sheets.queue_sync(
        restaurant_id, "ORDER_STATUS_CHANGED", order_id,
        {"order_number": order["order_number"], "restaurant_name": (restaurant or {}).get("name", ""),
         "customer_name": order["customer_name"], "customer_phone": order["customer_phone"],
         "order_type": order["order_type"], "items_text": items_text(order["items"]),
         "subtotal": order["subtotal"], "delivery_fee": order["delivery_fee"], "discount": order["discount"],
         "total": order["total"], "address": order.get("address") or "", "payment_method": order.get("payment_method", "Cash"),
         "status": new_status, "created_at": str(order["created_at"]), "updated_at": str(now)},
    )
    return {"ok": True, "order_number": order["order_number"], "status": new_status, "notified": bool(text)}


def _order_event_payload(order: dict) -> dict:
    return {
        "id": order.get("id") or str(order.get("_id")),
        "order_number": order["order_number"],
        "customer_name": order["customer_name"],
        "customer_phone": order["customer_phone"],
        "order_type": order["order_type"],
        "items": order["items"],
        "subtotal": order["subtotal"],
        "delivery_fee": order["delivery_fee"],
        "discount": order.get("discount", 0),
        "total": order["total"],
        "address": order.get("address"),
        "status": order["status"],
        "eta_min": order.get("eta_min"),
        "eta_max": order.get("eta_max"),
        "created_at": str(order.get("created_at")),
        "updated_at": str(order.get("updated_at")),
    }


async def _upsert_customer(restaurant_id: str, phone: Optional[str], name: Optional[str]) -> Optional[dict]:
    if not phone:
        return None
    customer = await db.customers.find_one({"restaurant_id": restaurant_id, "phone": phone})
    if customer:
        if name and customer.get("name") != name:
            await db.customers.update_one({"_id": customer["_id"]}, {"$set": {"name": name}})
            customer["name"] = name
        return customer
    now = datetime.now(timezone.utc)
    doc = {"restaurant_id": restaurant_id, "name": name, "phone": phone, "total_orders": 0,
           "total_spent": 0.0, "last_order_at": None, "created_at": now}
    result = await db.customers.insert_one(dict(doc))
    doc["_id"] = result.inserted_id
    await sheets.queue_sync(
        restaurant_id, "CUSTOMER_CREATED", str(result.inserted_id),
        {"customer_id": str(result.inserted_id), "name": name, "phone": phone, "total_orders": 0,
         "total_spent": 0, "last_order": "", "created_at": str(now)},
    )
    return doc


async def _bump_customer_stats(restaurant_id: str, customer: Optional[dict], amount: float, when: datetime) -> None:
    if not customer:
        return
    await db.customers.update_one(
        {"_id": customer["_id"]},
        {"$inc": {"total_orders": 1, "total_spent": amount}, "$set": {"last_order_at": when}},
    )
