"""Server-side cart. The frontend/LLM never owns cart state or prices."""

from datetime import datetime, timezone

from core.db import db, oid


async def get_cart(restaurant_id: str, conversation_id: str) -> dict:
    cart = await db.carts.find_one({"conversation_id": conversation_id})
    if not cart:
        cart = {
            "restaurant_id": restaurant_id,
            "conversation_id": conversation_id,
            "items": [],
            "order_type": None,
            "customer_name": None,
            "customer_phone": None,
            "address": None,
            "payment_method": "Cash",
            "upsell_offered": [],
            "upsell_declined": False,
            "updated_at": datetime.now(timezone.utc),
        }
        result = await db.carts.insert_one(dict(cart))
        cart["_id"] = result.inserted_id
    return cart


async def _save(conversation_id: str, fields: dict) -> dict:
    fields["updated_at"] = datetime.now(timezone.utc)
    await db.carts.update_one({"conversation_id": conversation_id}, {"$set": fields})
    return await db.carts.find_one({"conversation_id": conversation_id})


async def add_item(restaurant_id: str, conversation_id: str, item_name: str, quantity: int) -> dict:
    quantity = max(1, min(int(quantity or 1), 50))
    item = await db.menu_items.find_one(
        {"restaurant_id": restaurant_id, "name": {"$regex": f"^{_escape(item_name)}$", "$options": "i"}}
    )
    if not item:
        item = await db.menu_items.find_one(
            {"restaurant_id": restaurant_id, "name": {"$regex": _escape(item_name), "$options": "i"}}
        )
    if not item:
        return {"ok": False, "error": f"'{item_name}' is not on the menu. Use get_menu to see available items."}
    if not item.get("available", True):
        return {"ok": False, "error": f"{item['name']} is currently unavailable."}

    cart = await get_cart(restaurant_id, conversation_id)
    items = list(cart.get("items", []))
    item_id = str(item["_id"])
    for line in items:
        if line["item_id"] == item_id:
            line["quantity"] = min(line["quantity"] + quantity, 50)
            break
    else:
        items.append(
            {"item_id": item_id, "name": item["name"], "unit_price": float(item["price"]), "quantity": quantity}
        )
    cart = await _save(conversation_id, {"items": items})
    return {"ok": True, "added": {"name": item["name"], "quantity": quantity, "unit_price": float(item["price"])}, "cart": await summary(restaurant_id, conversation_id)}


async def remove_item(restaurant_id: str, conversation_id: str, item_name: str) -> dict:
    cart = await get_cart(restaurant_id, conversation_id)
    items = [i for i in cart.get("items", []) if i["name"].lower() != (item_name or "").lower()]
    if len(items) == len(cart.get("items", [])):
        return {"ok": False, "error": f"'{item_name}' is not in the cart."}
    await _save(conversation_id, {"items": items})
    return {"ok": True, "cart": await summary(restaurant_id, conversation_id)}


async def update_quantity(restaurant_id: str, conversation_id: str, item_name: str, quantity: int) -> dict:
    cart = await get_cart(restaurant_id, conversation_id)
    quantity = int(quantity or 0)
    items = []
    found = False
    for line in cart.get("items", []):
        if line["name"].lower() == (item_name or "").lower():
            found = True
            if quantity > 0:
                line["quantity"] = min(quantity, 50)
                items.append(line)
        else:
            items.append(line)
    if not found:
        return {"ok": False, "error": f"'{item_name}' is not in the cart."}
    await _save(conversation_id, {"items": items})
    return {"ok": True, "cart": await summary(restaurant_id, conversation_id)}


async def set_details(conversation_id: str, **fields) -> dict:
    allowed = {k: v for k, v in fields.items() if k in {"order_type", "customer_name", "customer_phone", "address", "payment_method"} and v}
    if "order_type" in allowed:
        allowed["order_type"] = str(allowed["order_type"]).lower()
        if allowed["order_type"] not in ("delivery", "pickup"):
            return {"ok": False, "error": "order_type must be 'delivery' or 'pickup'."}
    if not allowed:
        return {"ok": False, "error": "Nothing to update."}
    cart = await _save(conversation_id, allowed)
    return {"ok": True, "order_type": cart.get("order_type"), "customer_name": cart.get("customer_name"), "address": cart.get("address")}


async def mark_upsell(conversation_id: str, item_name: str) -> None:
    await db.carts.update_one({"conversation_id": conversation_id}, {"$addToSet": {"upsell_offered": item_name}})


async def decline_upsell(conversation_id: str) -> None:
    await db.carts.update_one({"conversation_id": conversation_id}, {"$set": {"upsell_declined": True}})


async def clear(conversation_id: str) -> None:
    await db.carts.update_one(
        {"conversation_id": conversation_id},
        {"$set": {"items": [], "upsell_offered": [], "upsell_declined": False, "updated_at": datetime.now(timezone.utc)}},
    )


async def summary(restaurant_id: str, conversation_id: str) -> dict:
    from services.orders import calculate_totals

    cart = await get_cart(restaurant_id, conversation_id)
    totals = await calculate_totals(restaurant_id, cart.get("items", []), cart.get("order_type"))
    return {
        "items": [
            {"name": i["name"], "quantity": i["quantity"], "unit_price": i["unit_price"], "line_total": i["unit_price"] * i["quantity"]}
            for i in cart.get("items", [])
        ],
        "order_type": cart.get("order_type"),
        "customer_name": cart.get("customer_name"),
        "customer_phone": cart.get("customer_phone"),
        "address": cart.get("address"),
        "upsell_offered": cart.get("upsell_offered", []),
        "upsell_declined": cart.get("upsell_declined", False),
        **totals,
    }


def _escape(text: str) -> str:
    import re

    return re.escape(text or "")
