"""Idempotent demo seed: Pizza Palace with a full menu, settings and an owner account."""

import logging
import os
from datetime import datetime, timezone

from core.db import db
from core.security import hash_password, verify_password

logger = logging.getLogger(__name__)

BURGER_IMG = "https://images.pexels.com/photos/17121731/pexels-photo-17121731.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
BURGER_IMG2 = "https://images.unsplash.com/photo-1603197095324-7ecbc1a05689?crop=entropy&cs=srgb&fm=jpg&q=85"
PIZZA_IMG = "https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?crop=entropy&cs=srgb&fm=jpg&q=85"
PIZZA_IMG2 = "https://images.pexels.com/photos/4109080/pexels-photo-4109080.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
FRIES_IMG = "https://images.pexels.com/photos/28992238/pexels-photo-28992238.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
FRIES_IMG2 = "https://images.unsplash.com/photo-1598679253544-2c97992403ea?crop=entropy&cs=srgb&fm=jpg&q=85"
COKE_IMG = "https://images.pexels.com/photos/33469209/pexels-photo-33469209.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
COKE_IMG2 = "https://images.unsplash.com/photo-1624552184280-9e9631bbeee9?crop=entropy&cs=srgb&fm=jpg&q=85"
BROWNIE_IMG = "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?crop=entropy&cs=srgb&fm=jpg&q=85"
BROWNIE_IMG2 = "https://images.pexels.com/photos/33312981/pexels-photo-33312981.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
BIRYANI_IMG = "https://images.pexels.com/photos/9738983/pexels-photo-9738983.jpeg"
TIKKA_IMG = "https://images.pexels.com/photos/6522616/pexels-photo-6522616.jpeg"

MENU = [
    ("Burgers", [
        ("Zinger Burger", 650, "Crispy fried chicken fillet, lettuce and mayo in a toasted bun", BURGER_IMG),
        ("Chicken Cheese Burger", 720, "Grilled chicken patty with melted cheddar", BURGER_IMG2),
        ("Beef Tikka Burger", 780, "Spiced beef patty with tikka sauce", TIKKA_IMG),
    ]),
    ("Pizza", [
        ("Large Pizza", 1499, "Large hand-tossed pizza with your favourite toppings", PIZZA_IMG),
        ("Chicken Tikka Pizza (Medium)", 1150, "Medium pizza loaded with chicken tikka and capsicum", PIZZA_IMG2),
        ("Pepperoni Pizza (Small)", 850, "Small pizza with pepperoni and mozzarella", PIZZA_IMG),
    ]),
    ("Rice", [
        ("Chicken Biryani", 480, "Aromatic Sindhi-style chicken biryani", BIRYANI_IMG),
    ]),
    ("Fries", [
        ("Fries", 250, "Golden crispy salted fries", FRIES_IMG),
        ("Loaded Cheese Fries", 420, "Fries topped with cheese sauce and jalapenos", FRIES_IMG2),
    ]),
    ("Drinks", [
        ("Coke", 120, "Chilled 345ml can", COKE_IMG),
        ("Coke 1.5L", 250, "Family size bottle", COKE_IMG2),
        ("Fresh Lime", 180, "Freshly squeezed lime soda", COKE_IMG),
    ]),
    ("Desserts", [
        ("Brownie", 350, "Warm fudge brownie", BROWNIE_IMG),
        ("Chocolate Lava Cake", 450, "Molten chocolate centre", BROWNIE_IMG2),
    ]),
]

ADDONS = [("Fries", 250), ("Coke", 120), ("Extra Cheese", 150), ("Garlic Mayo Dip", 80)]
UPSELL_FOR = {"Zinger Burger", "Chicken Cheese Burger", "Beef Tikka Burger", "Large Pizza",
              "Chicken Tikka Pizza (Medium)", "Pepperoni Pizza (Small)", "Chicken Biryani"}


async def seed_demo() -> dict:
    if os.environ.get("DEMO_MODE", "true").lower() != "true":
        return {"seeded": False}

    now = datetime.now(timezone.utc)
    restaurant = await db.restaurants.find_one({"slug": "pizza-palace"})
    if not restaurant:
        result = await db.restaurants.insert_one(
            {
                "name": "Pizza Palace",
                "slug": "pizza-palace",
                "logo_url": PIZZA_IMG,
                "description": "Burgers, pizza and desi favourites delivered hot across Islamabad.",
                "phone": "+92 51 111 222 333",
                "whatsapp_number": "+92 300 1234567",
                "address": "Plot 14, F-7 Markaz",
                "city": "Islamabad",
                "currency": "PKR",
                "ai_greeting": "Assalam o Alaikum! Pizza Palace mein khush aamdeed. Aap kya order karna chahenge?",
                "business_rules": "Cash on delivery only. Delivery within Islamabad city limits.",
                "demo": True,
                "created_at": now,
            }
        )
        restaurant = await db.restaurants.find_one({"_id": result.inserted_id})
    restaurant_id = str(restaurant["_id"])

    if not await db.restaurant_settings.find_one({"restaurant_id": restaurant_id}):
        await db.restaurant_settings.insert_one(
            {
                "restaurant_id": restaurant_id,
                "opening_hours": [{"day": d, "open": "11:00", "close": "23:59", "closed": False} for d in range(7)],
                "delivery_areas": ["F-6", "F-7", "F-8", "F-10", "Blue Area", "G-9"],
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

    addon_ids: dict[str, str] = {}
    for name, price in ADDONS:
        existing = await db.menu_addons.find_one({"restaurant_id": restaurant_id, "name": name})
        if existing:
            addon_ids[name] = str(existing["_id"])
        else:
            res = await db.menu_addons.insert_one({"restaurant_id": restaurant_id, "name": name, "price": float(price), "available": True})
            addon_ids[name] = str(res.inserted_id)

    upsell_ids = [addon_ids["Fries"], addon_ids["Coke"], addon_ids["Garlic Mayo Dip"]]

    for order, (category_name, items) in enumerate(MENU):
        category = await db.menu_categories.find_one({"restaurant_id": restaurant_id, "name": category_name})
        if not category:
            res = await db.menu_categories.insert_one(
                {"restaurant_id": restaurant_id, "name": category_name, "sort_order": order, "active": True}
            )
            category = {"_id": res.inserted_id}
        category_id = str(category["_id"])
        for idx, (name, price, description, image) in enumerate(items):
            if await db.menu_items.find_one({"restaurant_id": restaurant_id, "name": name}):
                continue
            await db.menu_items.insert_one(
                {
                    "restaurant_id": restaurant_id,
                    "category_id": category_id,
                    "name": name,
                    "description": description,
                    "price": float(price),
                    "image_url": image,
                    "available": True,
                    "addon_ids": upsell_ids if name in UPSELL_FOR else [],
                    "sort_order": idx,
                }
            )

    if not await db.whatsapp_sessions.find_one({"restaurant_id": restaurant_id}):
        await db.whatsapp_sessions.insert_one(
            {"restaurant_id": restaurant_id, "provider": os.environ.get("WHATSAPP_PROVIDER", "simulator"),
             "status": "disconnected", "connected_number": None, "qr_payload": None,
             "last_connected_at": None, "updated_at": now}
        )

    if not await db.google_sheet_connections.find_one({"restaurant_id": restaurant_id}):
        await db.google_sheet_connections.insert_one(
            {"restaurant_id": restaurant_id, "status": "not_connected",
             "spreadsheet_id": os.environ.get("GOOGLE_SHEET_ID") or None, "spreadsheet_name": None,
             "service_account_email": None, "last_sync_at": None, "last_error": None, "updated_at": now}
        )

    email = os.environ.get("DEMO_OWNER_EMAIL", "owner@pizzapalace.pk").lower()
    password = os.environ.get("DEMO_OWNER_PASSWORD", "Pizza123!")
    user = await db.users.find_one({"email": email})
    if not user:
        await db.users.insert_one(
            {"email": email, "password_hash": hash_password(password), "name": "Ali Raza",
             "role": "owner", "restaurant_id": restaurant_id, "created_at": now}
        )
    else:
        updates = {}
        if not verify_password(password, user["password_hash"]):
            updates["password_hash"] = hash_password(password)
        if user.get("restaurant_id") != restaurant_id:
            updates["restaurant_id"] = restaurant_id
        if updates:
            await db.users.update_one({"_id": user["_id"]}, {"$set": updates})

    logger.info("demo seed ready: restaurant=%s owner=%s", restaurant_id, email)
    return {"seeded": True, "restaurant_id": restaurant_id, "owner_email": email}
