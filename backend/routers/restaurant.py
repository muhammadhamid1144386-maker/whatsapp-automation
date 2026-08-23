from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.db import db, oid
from core.security import audit, get_current_user, tenant
from models import OpeningHour, OrderStatus, Restaurant, RestaurantSettings
from services import sheets
from services.orders import is_open
from services.whatsapp import get_whatsapp_provider

router = APIRouter(prefix="/api", tags=["restaurant"])

DONE = {OrderStatus.DELIVERED.value}
OPEN_STATES = [OrderStatus.NEW.value, OrderStatus.CONFIRMED.value, OrderStatus.PREPARING.value,
               OrderStatus.READY.value, OrderStatus.OUT_FOR_DELIVERY.value]


class ProfileBody(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    currency: Optional[str] = None
    ai_greeting: Optional[str] = None
    business_rules: Optional[str] = None


class SettingsBody(BaseModel):
    opening_hours: Optional[List[OpeningHour]] = None
    delivery_areas: Optional[List[str]] = None
    delivery_fee: Optional[float] = None
    min_order: Optional[float] = None
    prep_time_min: Optional[int] = None
    prep_time_max: Optional[int] = None
    delivery_time_min: Optional[int] = None
    delivery_time_max: Optional[int] = None
    allow_orders_when_closed: Optional[bool] = None
    upsell_enabled: Optional[bool] = None
    ai_active: Optional[bool] = None


@router.get("/restaurant")
async def get_restaurant(restaurant_id: str = Depends(tenant)):
    restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
    settings = await db.restaurant_settings.find_one({"restaurant_id": restaurant_id})
    open_now, opens_at = is_open(settings or {})
    return {
        "restaurant": Restaurant.from_mongo(restaurant).model_dump(),
        "settings": RestaurantSettings.from_mongo(settings).model_dump() if settings else None,
        "open_now": open_now,
        "opens_at": opens_at,
    }


@router.put("/restaurant")
async def update_restaurant(body: ProfileBody, restaurant_id: str = Depends(tenant), user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.restaurants.update_one({"_id": oid(restaurant_id)}, {"$set": updates})
        await audit(restaurant_id, user["email"], "restaurant.update", updates)
    restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
    return Restaurant.from_mongo(restaurant).model_dump()


@router.put("/restaurant/settings")
async def update_settings(body: SettingsBody, restaurant_id: str = Depends(tenant), user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "opening_hours" in updates:
        updates["opening_hours"] = [h if isinstance(h, dict) else h.model_dump() for h in updates["opening_hours"]]
    if updates:
        await db.restaurant_settings.update_one({"restaurant_id": restaurant_id}, {"$set": updates}, upsert=True)
        await audit(restaurant_id, user["email"], "settings.update", {k: str(v) for k, v in updates.items()})
    settings = await db.restaurant_settings.find_one({"restaurant_id": restaurant_id})
    return RestaurantSettings.from_mongo(settings).model_dump()


@router.get("/analytics/summary")
async def analytics_summary(restaurant_id: str = Depends(tenant)):
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=5)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    async def agg(match: dict) -> dict:
        rows = await db.orders.aggregate([
            {"$match": match},
            {"$group": {"_id": None, "count": {"$sum": 1}, "sales": {"$sum": "$total"}}},
        ]).to_list(1)
        row = rows[0] if rows else {"count": 0, "sales": 0}
        return {"count": row["count"], "sales": round(row.get("sales", 0) or 0, 2)}

    base = {"restaurant_id": restaurant_id, "status": {"$nin": [OrderStatus.REJECTED.value, OrderStatus.CANCELLED.value]}}
    today = await agg({**base, "created_at": {"$gte": start_of_day}})
    week = await agg({**base, "created_at": {"$gte": week_start}})
    month = await agg({**base, "created_at": {"$gte": month_start}})
    all_time = await agg(base)

    pending = await db.orders.count_documents({"restaurant_id": restaurant_id, "status": {"$in": OPEN_STATES}})
    completed_today = await db.orders.count_documents({"restaurant_id": restaurant_id, "status": {"$in": list(DONE)}, "created_at": {"$gte": start_of_day}})
    avg = round(today["sales"] / today["count"], 2) if today["count"] else 0

    top_rows = await db.order_items.aggregate([
        {"$match": {"restaurant_id": restaurant_id}},
        {"$group": {"_id": "$name", "quantity": {"$sum": "$quantity"}, "revenue": {"$sum": "$line_total"}}},
        {"$sort": {"quantity": -1}},
        {"$limit": 5},
    ]).to_list(5)

    daily_rows = await db.orders.aggregate([
        {"$match": {**base, "created_at": {"$gte": week_start}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "orders": {"$sum": 1}, "sales": {"$sum": "$total"}}},
        {"$sort": {"_id": 1}},
    ]).to_list(14)

    session = await get_whatsapp_provider().get_status(restaurant_id)
    sync = await sheets.stats(restaurant_id)
    connection = await sheets.get_connection(restaurant_id)
    customers = await db.customers.count_documents({"restaurant_id": restaurant_id})

    return {
        "today_orders": today["count"],
        "today_sales": today["sales"],
        "pending_orders": pending,
        "completed_orders": completed_today,
        "average_order_value": avg,
        "week_sales": week["sales"],
        "month_sales": month["sales"],
        "lifetime_orders": all_time["count"],
        "lifetime_sales": all_time["sales"],
        "total_customers": customers,
        "top_items": [{"name": r["_id"], "quantity": r["quantity"], "revenue": round(r["revenue"], 2)} for r in top_rows],
        "daily": [{"date": r["_id"], "orders": r["orders"], "sales": round(r["sales"], 2)} for r in daily_rows],
        "whatsapp": {"status": session.get("status"), "connected_number": session.get("connected_number")},
        "google_sheets": {"status": connection.get("status"), "last_sync_at": connection.get("last_sync_at"), **sync},
        "currency": "PKR",
    }
