"""The AI restaurant agent: system prompt, controlled backend tools, tool dispatch.

The LLM never touches the database directly. It can only call the validated tools
declared here, and every price/total comes back from the backend.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from core.db import db, oid
from services import cart as cart_service
from services import orders as order_service
from services.ai import get_ai_provider

logger = logging.getLogger(__name__)

TOOLS = [
    {"type": "function", "function": {"name": "get_restaurant_info", "description": "Restaurant name, address, city, phone, opening hours, delivery fee, minimum order, prep and delivery times, and whether it is open right now.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_menu", "description": "The full menu grouped by category with exact prices and availability.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_menu_category", "description": "Items in one menu category.", "parameters": {"type": "object", "properties": {"category": {"type": "string"}}, "required": ["category"]}}},
    {"type": "function", "function": {"name": "check_item_availability", "description": "Check whether a menu item exists and is currently available.", "parameters": {"type": "object", "properties": {"item_name": {"type": "string"}}, "required": ["item_name"]}}},
    {"type": "function", "function": {"name": "get_customer_history", "description": "Recent order history and totals for this customer.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_cart", "description": "Current server-side cart with backend-calculated totals.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "add_to_cart", "description": "Add a menu item to the cart. Use the exact menu item name.", "parameters": {"type": "object", "properties": {"item_name": {"type": "string"}, "quantity": {"type": "integer"}}, "required": ["item_name"]}}},
    {"type": "function", "function": {"name": "remove_from_cart", "description": "Remove an item from the cart.", "parameters": {"type": "object", "properties": {"item_name": {"type": "string"}}, "required": ["item_name"]}}},
    {"type": "function", "function": {"name": "update_cart_quantity", "description": "Set the quantity of a cart item. Quantity 0 removes it.", "parameters": {"type": "object", "properties": {"item_name": {"type": "string"}, "quantity": {"type": "integer"}}, "required": ["item_name", "quantity"]}}},
    {"type": "function", "function": {"name": "calculate_cart", "description": "Authoritative subtotal, delivery fee, total and estimated time. Always use these numbers.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "calculate_delivery_fee", "description": "Delivery fee configured by the restaurant.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "set_order_details", "description": "Save delivery/pickup choice and the customer's name, phone and address.", "parameters": {"type": "object", "properties": {"order_type": {"type": "string", "enum": ["delivery", "pickup"]}, "customer_name": {"type": "string"}, "customer_phone": {"type": "string"}, "address": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "record_upsell_declined", "description": "Call this once the customer declines an add-on suggestion so it is never suggested again.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "create_order", "description": "Create the order. ONLY call after showing the full summary and receiving explicit confirmation.", "parameters": {"type": "object", "properties": {"customer_confirmed": {"type": "boolean", "description": "Must be true; set only when the customer explicitly confirmed."}}, "required": ["customer_confirmed"]}}},
    {"type": "function", "function": {"name": "get_order_status", "description": "Status of an order. Omit order_number for the customer's latest order.", "parameters": {"type": "object", "properties": {"order_number": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "request_human_handoff", "description": "Hand the conversation to restaurant staff and stop AI replies.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}}}},
]

SYSTEM_PROMPT = """You are the AI ordering assistant for {restaurant_name}, a restaurant in {city}, Pakistan.

Your job: help customers browse the menu, build an order, answer restaurant questions, collect the details you need, confirm the order and report order status.

HARD RULES
- Only use restaurant information returned by your tools. Never invent menu items, prices, discounts, delivery fees, opening hours, delivery times or order status.
- Never do arithmetic yourself. Call calculate_cart and quote its numbers exactly.
- Currency is always PKR.
- Keep every reply short and conversational, like a WhatsApp message. 1-4 short lines. No long paragraphs, no markdown tables, no bullet symbols other than a simple dash.
- Language: reply in the SAME language the customer used. Roman Urdu in -> Roman Urdu out. Urdu script in -> Urdu script out. English in -> English out. The customer's current language is: {language}.
- Ask for quantity only when it is genuinely unclear.

ORDERING FLOW
1. Greet, then help pick items. Call add_to_cart for each item.
2. Upselling: after items are added you may suggest exactly ONE relevant complementary item that is on the menu and available. Suggest it at most once. If the customer declines, call record_upsell_declined and never suggest again.
3. Ask "Delivery or pickup?" and save it with set_order_details.
4. For delivery collect name and full address. For pickup collect only name. Do not ask for anything else. The phone number is already known.
5. Call calculate_cart, then show the summary: each item with quantity and line total, subtotal, delivery fee if delivery, total, and the estimated time returned by the backend.
6. Ask for explicit confirmation.
7. Only after a clear yes, call create_order with customer_confirmed true. Then tell the customer the order number and estimated time returned by the tool.

OTHER
- If the restaurant is closed, say so with the opening time and do not place an order.
- If a tool returns an error, tell the customer plainly what is missing and ask for it.
- If the customer asks for a human, complains, or asks for something you cannot do, call request_human_handoff and tell them staff will reply shortly.

CONTEXT
{context}
"""


@dataclass
class AgentContext:
    restaurant: dict
    settings: dict
    conversation: dict
    customer: Optional[dict]
    language: str

    @property
    def restaurant_id(self) -> str:
        return str(self.restaurant["_id"])

    @property
    def conversation_id(self) -> str:
        return str(self.conversation["_id"])

    @property
    def phone(self) -> str:
        return self.conversation["phone"]


async def menu_snapshot(restaurant_id: str) -> list[dict]:
    categories = await db.menu_categories.find({"restaurant_id": restaurant_id, "active": True}).sort("sort_order", 1).to_list(50)
    out = []
    for category in categories:
        items = await db.menu_items.find({"restaurant_id": restaurant_id, "category_id": str(category["_id"])}).sort("sort_order", 1).to_list(100)
        out.append(
            {
                "category": category["name"],
                "items": [
                    {"name": i["name"], "price": float(i["price"]), "available": i.get("available", True), "description": i.get("description")}
                    for i in items
                ],
            }
        )
    return out


def _compact_menu(snapshot: list[dict]) -> str:
    lines = []
    for group in snapshot:
        available = [f"{i['name']} PKR {i['price']:.0f}{'' if i['available'] else ' (UNAVAILABLE)'}" for i in group["items"]]
        if available:
            lines.append(f"{group['category']}: " + "; ".join(available))
    return "\n".join(lines)


async def build_context(ctx: AgentContext) -> str:
    snapshot = await menu_snapshot(ctx.restaurant_id)
    open_now, opens_at = order_service.is_open(ctx.settings)
    cart = await cart_service.summary(ctx.restaurant_id, ctx.conversation_id)
    prep = f"{ctx.settings.get('prep_time_min', 20)}-{ctx.settings.get('prep_time_max', 30)} minutes"
    delivery_eta = order_service.eta_for(ctx.settings, "delivery")
    history = ""
    if ctx.customer and ctx.customer.get("total_orders"):
        last = await db.orders.find({"restaurant_id": ctx.restaurant_id, "customer_id": str(ctx.customer["_id"])}).sort("created_at", -1).to_list(1)
        if last:
            items = ", ".join(f"{i['quantity']}x {i['name']}" for i in last[0]["items"])
            history = f"Returning customer ({ctx.customer['total_orders']} previous orders). Last order: {items}."
    recent = await db.messages.find({"conversation_id": ctx.conversation_id}).sort("created_at", -1).to_list(12)
    transcript = "\n".join(
        f"{'Customer' if m['sender'] == 'customer' else 'You'}: {m['body']}" for m in reversed(recent)
    )
    return f"""MENU (authoritative prices):
{_compact_menu(snapshot)}

RESTAURANT: open now = {open_now}{'' if open_now else f', opens at {opens_at}'}. Delivery fee PKR {ctx.settings.get('delivery_fee', 150):.0f}. Minimum order PKR {ctx.settings.get('min_order', 0):.0f}. Preparation {prep}. Delivery ETA {delivery_eta[0]}-{delivery_eta[1]} minutes. Pickup ETA {prep}.
CUSTOMER: phone {ctx.phone}. {history or 'New customer.'}
CART RIGHT NOW: {cart['items'] or 'empty'} | order_type={cart['order_type']} | name={cart['customer_name']} | address={cart['address']} | subtotal={cart['subtotal']} | delivery_fee={cart['delivery_fee']} | total={cart['total']} | upsell_declined={cart['upsell_declined']}
CONVERSATION STATE: {ctx.conversation.get('state')}

RECENT TRANSCRIPT:
{transcript or '(no earlier messages)'}"""


def make_dispatcher(ctx: AgentContext):
    rid = ctx.restaurant_id
    cid = ctx.conversation_id

    async def dispatch(name: str, args: dict) -> dict:
        if name == "get_restaurant_info":
            open_now, opens_at = order_service.is_open(ctx.settings)
            return {
                "name": ctx.restaurant["name"], "address": ctx.restaurant.get("address"),
                "city": ctx.restaurant.get("city"), "phone": ctx.restaurant.get("phone"),
                "currency": ctx.restaurant.get("currency", "PKR"),
                "open_now": open_now, "opens_at": opens_at,
                "opening_hours": ctx.settings.get("opening_hours", []),
                "delivery_fee": ctx.settings.get("delivery_fee"), "min_order": ctx.settings.get("min_order"),
                "delivery_areas": ctx.settings.get("delivery_areas", []),
                "prep_time": f"{ctx.settings.get('prep_time_min')}-{ctx.settings.get('prep_time_max')} minutes",
                "delivery_eta": "%s-%s minutes" % order_service.eta_for(ctx.settings, "delivery"),
                "pickup_eta": "%s-%s minutes" % order_service.eta_for(ctx.settings, "pickup"),
            }

        if name == "get_menu":
            return {"menu": await menu_snapshot(rid), "currency": "PKR"}

        if name == "get_menu_category":
            wanted = (args.get("category") or "").lower()
            snapshot = await menu_snapshot(rid)
            match = next((g for g in snapshot if wanted in g["category"].lower()), None)
            return match or {"ok": False, "error": f"No category named '{args.get('category')}'.", "categories": [g["category"] for g in snapshot]}

        if name == "check_item_availability":
            item = await db.menu_items.find_one({"restaurant_id": rid, "name": {"$regex": args.get("item_name", ""), "$options": "i"}})
            if not item:
                return {"exists": False}
            return {"exists": True, "name": item["name"], "price": float(item["price"]), "available": item.get("available", True)}

        if name == "get_customer_history":
            if not ctx.customer:
                return {"new_customer": True, "orders": []}
            recent = await db.orders.find({"restaurant_id": rid, "customer_id": str(ctx.customer["_id"])}).sort("created_at", -1).to_list(3)
            return {
                "new_customer": False, "name": ctx.customer.get("name"),
                "total_orders": ctx.customer.get("total_orders", 0), "total_spent": ctx.customer.get("total_spent", 0),
                "orders": [{"order_number": o["order_number"], "status": o["status"],
                            "items": [f"{i['quantity']}x {i['name']}" for i in o["items"]], "total": o["total"]} for o in recent],
            }

        if name in ("get_cart", "calculate_cart"):
            return await cart_service.summary(rid, cid)

        if name == "add_to_cart":
            result = await cart_service.add_item(rid, cid, args.get("item_name", ""), args.get("quantity") or 1)
            if result.get("ok"):
                await db.conversations.update_one({"_id": oid(cid)}, {"$set": {"state": "SELECTING_ITEMS"}})
            return result

        if name == "remove_from_cart":
            return await cart_service.remove_item(rid, cid, args.get("item_name", ""))

        if name == "update_cart_quantity":
            return await cart_service.update_quantity(rid, cid, args.get("item_name", ""), args.get("quantity", 0))

        if name == "calculate_delivery_fee":
            return {"delivery_fee": float(ctx.settings.get("delivery_fee", 150)), "currency": "PKR"}

        if name == "set_order_details":
            result = await cart_service.set_details(cid, **args)
            if result.get("ok"):
                state = "COLLECTING_ADDRESS" if args.get("order_type") == "delivery" else "CART_REVIEW"
                await db.conversations.update_one({"_id": oid(cid)}, {"$set": {"state": state}})
            return result

        if name == "record_upsell_declined":
            await cart_service.decline_upsell(cid)
            return {"ok": True}

        if name == "create_order":
            if not args.get("customer_confirmed"):
                return {"ok": False, "error": "Show the full order summary and get explicit confirmation before calling create_order."}
            await db.conversations.update_one({"_id": oid(cid)}, {"$set": {"state": "CONFIRMING_ORDER"}})
            return await order_service.create_order(rid, cid, language=ctx.language)

        if name == "get_order_status":
            query = {"restaurant_id": rid}
            if args.get("order_number"):
                query["order_number"] = args["order_number"].upper()
            elif ctx.customer:
                query["customer_id"] = str(ctx.customer["_id"])
            else:
                query["customer_phone"] = ctx.phone
            order = await db.orders.find_one(query, sort=[("created_at", -1)])
            if not order:
                return {"found": False}
            await db.conversations.update_one({"_id": oid(cid)}, {"$set": {"state": "ORDER_STATUS"}})
            return {"found": True, "order_number": order["order_number"], "status": order["status"],
                    "order_type": order["order_type"], "total": order["total"],
                    "eta": f"{order['eta_min']}-{order['eta_max']} minutes"}

        if name == "request_human_handoff":
            await db.conversations.update_one(
                {"_id": oid(cid)}, {"$set": {"ai_active": False, "state": "HUMAN_HANDOFF"}}
            )
            from services.realtime import broker, dashboard_channel

            await broker.publish(dashboard_channel(rid), "HUMAN_HANDOFF", {"conversation_id": cid, "phone": ctx.phone, "reason": args.get("reason")})
            return {"ok": True, "message": "Restaurant staff have been notified and will reply shortly."}

        return {"ok": False, "error": f"Unknown tool {name}"}

    return dispatch


FALLBACK = {
    "en": "Sorry, I'm having trouble right now. A team member from the restaurant will reply to you shortly.",
    "roman_ur": "Maazrat, mujhe abhi thori dikkat ho rahi hai. Restaurant ka staff aap ko jald reply karega.",
    "ur": "معذرت، مجھے ابھی کچھ مسئلہ ہو رہا ہے۔ ریسٹورنٹ کا اسٹاف آپ کو جلد جواب دے گا۔",
}


async def respond(ctx: AgentContext, user_text: str) -> list[str]:
    provider = get_ai_provider()
    system_message = SYSTEM_PROMPT.format(
        restaurant_name=ctx.restaurant["name"],
        city=ctx.restaurant.get("city") or "Pakistan",
        language={"en": "English", "ur": "Urdu script", "roman_ur": "Roman Urdu"}.get(ctx.language, "English"),
        context=await build_context(ctx),
    )
    try:
        replies = await provider.generate_response(
            system_message=system_message,
            session_id=ctx.conversation_id,
            user_text=user_text,
            tools=TOOLS,
            dispatch=make_dispatcher(ctx),
        )
    except Exception as exc:
        # Infrastructure failure (provider down, quota exhausted). Keep the AI enabled so the
        # conversation self-heals on the next message, but alert staff so they can step in.
        logger.exception("AI provider failed: %s", exc)
        from services.realtime import broker, dashboard_channel

        await broker.publish(
            dashboard_channel(ctx.restaurant_id), "AI_ERROR",
            {"conversation_id": ctx.conversation_id, "phone": ctx.phone, "reason": str(exc)[:180]},
        )
        return [FALLBACK.get(ctx.language, FALLBACK["en"])]
    return replies or [FALLBACK.get(ctx.language, FALLBACK["en"])]
