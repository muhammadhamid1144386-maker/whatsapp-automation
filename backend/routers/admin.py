"""Platform-owner (super admin) panel. Every route is platform-scoped, never tenant-scoped."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.db import db, oid
from core.security import audit, require_platform_admin
from models import OrderStatus
from services import clients, subscriptions

router = APIRouter(prefix="/api/admin", tags=["admin"])

CANCELLED = [OrderStatus.REJECTED.value, OrderStatus.CANCELLED.value]


class ClientBody(BaseModel):
    restaurant_name: str = Field(min_length=2, max_length=80)
    owner_name: str = Field(min_length=2, max_length=80)
    email: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    amount: float = 5000
    billing_period: str = "monthly"


class PlanBody(BaseModel):
    plan_name: Optional[str] = None
    amount: Optional[float] = None
    billing_period: Optional[str] = None
    grace_days: Optional[int] = None
    current_period_end: Optional[datetime] = None


class PaymentBody(BaseModel):
    amount: float
    method: str = "Cash"
    note: str = ""


async def _client_row(restaurant: dict) -> dict:
    restaurant_id = str(restaurant["_id"])
    sub = subscriptions.summarise(await subscriptions.get_or_create(restaurant_id))
    owner = await db.users.find_one({"restaurant_id": restaurant_id, "platform_role": None})
    orders = await db.orders.count_documents({"restaurant_id": restaurant_id, "status": {"$nin": CANCELLED}})
    return {
        "id": restaurant_id,
        "name": restaurant["name"],
        "slug": restaurant["slug"],
        "city": restaurant.get("city"),
        "phone": restaurant.get("phone"),
        "whatsapp_number": restaurant.get("whatsapp_number"),
        "demo": restaurant.get("demo", False),
        "created_at": restaurant.get("created_at"),
        "owner_email": (owner or {}).get("email"),
        "owner_name": (owner or {}).get("name"),
        "orders": orders,
        "subscription": sub,
    }


@router.get("/overview")
async def overview(admin: dict = Depends(require_platform_admin)):
    restaurants = await db.restaurants.find({}).sort("created_at", -1).to_list(500)
    rows = [await _client_row(r) for r in restaurants]

    active = [r for r in rows if r["subscription"]["status"] == "active"]
    grace = [r for r in rows if r["subscription"]["status"] == "grace"]
    blocked = [r for r in rows if r["subscription"]["status"] == "blocked"]
    expiring = sorted(
        [r for r in rows if r["subscription"]["status"] in ("active", "grace") and r["subscription"]["days_left"] <= 7],
        key=lambda r: r["subscription"]["days_left"],
    )
    monthly_value = sum(
        r["subscription"]["amount"] / {"monthly": 1, "quarterly": 3, "yearly": 12}.get(r["subscription"]["billing_period"], 1)
        for r in rows if r["subscription"]["status"] in ("active", "grace")
    )
    outstanding = sum(r["subscription"]["amount"] for r in rows if r["subscription"]["status"] in ("grace", "blocked"))
    collected_rows = await db.subscription_payments.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}]
    ).to_list(1)
    collected = collected_rows[0] if collected_rows else {"total": 0, "count": 0}

    return {
        "total_clients": len(rows),
        "active_clients": len(active),
        "grace_clients": len(grace),
        "blocked_clients": len(blocked),
        "monthly_recurring": round(monthly_value, 2),
        "outstanding": round(outstanding, 2),
        "collected_total": round(collected.get("total", 0) or 0, 2),
        "payments_recorded": collected.get("count", 0),
        "expiring_soon": expiring[:10],
        "recent_clients": rows[:5],
        "currency": "PKR",
    }


@router.get("/clients")
async def list_clients(
    admin: dict = Depends(require_platform_admin),
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(200, le=500),
):
    query: dict = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
            {"slug": {"$regex": search, "$options": "i"}},
        ]
    restaurants = await db.restaurants.find(query).sort("created_at", -1).to_list(limit)
    rows = [await _client_row(r) for r in restaurants]
    if status and status != "ALL":
        rows = [r for r in rows if r["subscription"]["status"] == status]
    return rows


@router.post("/clients")
async def create_client(body: ClientBody, admin: dict = Depends(require_platform_admin)):
    result = await clients.provision(
        restaurant_name=body.restaurant_name.strip(),
        owner_name=body.owner_name.strip(),
        email=body.email,
        city=body.city,
        phone=body.phone,
        whatsapp_number=body.whatsapp_number,
        amount=body.amount,
        billing_period=body.billing_period,
        created_by=admin["email"],
    )
    await audit(result["restaurant_id"], admin["email"], "admin.client.create", {"name": body.restaurant_name})
    restaurant = await db.restaurants.find_one({"_id": oid(result["restaurant_id"])})
    return {**await _client_row(restaurant), "credentials": {"email": result["email"], "password": result["password"]}}


@router.get("/clients/{restaurant_id}")
async def client_detail(restaurant_id: str, admin: dict = Depends(require_platform_admin)):
    restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Client not found")
    row = await _client_row(restaurant)
    credentials = await db.client_credentials.find_one({"restaurant_id": restaurant_id})
    payments = await db.subscription_payments.find({"restaurant_id": restaurant_id}).sort("created_at", -1).to_list(50)
    revenue_rows = await db.orders.aggregate([
        {"$match": {"restaurant_id": restaurant_id, "status": {"$nin": CANCELLED}}},
        {"$group": {"_id": None, "sales": {"$sum": "$total"}, "count": {"$sum": 1}}},
    ]).to_list(1)
    revenue = revenue_rows[0] if revenue_rows else {"sales": 0, "count": 0}
    alerts = await db.admin_alerts.find({"restaurant_id": restaurant_id}).sort("created_at", -1).to_list(25)
    return {
        **row,
        "credentials": {
            "email": (credentials or {}).get("email") or row.get("owner_email"),
            "password": (credentials or {}).get("password"),
            "issued_at": (credentials or {}).get("issued_at"),
        },
        "payments": [
            {"id": str(p["_id"]), "amount": p["amount"], "method": p.get("method"), "note": p.get("note"),
             "period_start": p.get("period_start"), "period_end": p.get("period_end"),
             "recorded_by": p.get("recorded_by"), "created_at": p["created_at"]}
            for p in payments
        ],
        "usage": {"orders": revenue.get("count", 0), "gmv": round(revenue.get("sales", 0) or 0, 2),
                  "customers": await db.customers.count_documents({"restaurant_id": restaurant_id}),
                  "menu_items": await db.menu_items.count_documents({"restaurant_id": restaurant_id})},
        "alerts": [
            {"id": str(a["_id"]), "kind": a["kind"], "severity": a["severity"], "message": a["message"],
             "read": a.get("read", False), "created_at": a["created_at"]}
            for a in alerts
        ],
    }


@router.post("/clients/{restaurant_id}/regenerate-password")
async def regenerate(restaurant_id: str, admin: dict = Depends(require_platform_admin)):
    if not await db.restaurants.find_one({"_id": oid(restaurant_id)}):
        raise HTTPException(status_code=404, detail="Client not found")
    result = await clients.regenerate_password(restaurant_id, admin["email"])
    await audit(restaurant_id, admin["email"], "admin.client.password_reset")
    return result


@router.put("/clients/{restaurant_id}/subscription")
async def update_subscription(restaurant_id: str, body: PlanBody, admin: dict = Depends(require_platform_admin)):
    if not await db.restaurants.find_one({"_id": oid(restaurant_id)}):
        raise HTTPException(status_code=404, detail="Client not found")
    if body.billing_period and body.billing_period not in subscriptions.PERIOD_MONTHS:
        raise HTTPException(status_code=400, detail="Billing period must be monthly, quarterly or yearly")
    sub = await subscriptions.update_plan(restaurant_id, **body.model_dump(exclude_none=True))
    await audit(restaurant_id, admin["email"], "admin.subscription.update", body.model_dump(exclude_none=True, mode="json"))
    return sub


@router.post("/clients/{restaurant_id}/payment")
async def record_payment(restaurant_id: str, body: PaymentBody, admin: dict = Depends(require_platform_admin)):
    if not await db.restaurants.find_one({"_id": oid(restaurant_id)}):
        raise HTTPException(status_code=404, detail="Client not found")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")
    sub = await subscriptions.record_payment(restaurant_id, body.amount, body.method, body.note, admin["email"])
    await audit(restaurant_id, admin["email"], "admin.payment.record", {"amount": body.amount})
    return sub


@router.post("/clients/{restaurant_id}/block")
async def block(restaurant_id: str, admin: dict = Depends(require_platform_admin)):
    if not await db.restaurants.find_one({"_id": oid(restaurant_id)}):
        raise HTTPException(status_code=404, detail="Client not found")
    sub = await subscriptions.set_status(restaurant_id, "blocked", admin["email"])
    await audit(restaurant_id, admin["email"], "admin.client.block")
    return sub


@router.post("/clients/{restaurant_id}/unblock")
async def unblock(restaurant_id: str, admin: dict = Depends(require_platform_admin)):
    if not await db.restaurants.find_one({"_id": oid(restaurant_id)}):
        raise HTTPException(status_code=404, detail="Client not found")
    sub = await subscriptions.set_status(restaurant_id, "active", admin["email"])
    await audit(restaurant_id, admin["email"], "admin.client.unblock")
    return sub


@router.delete("/clients/{restaurant_id}")
async def delete_client(restaurant_id: str, admin: dict = Depends(require_platform_admin)):
    restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
    if not restaurant:
        raise HTTPException(status_code=404, detail="Client not found")
    if restaurant.get("demo"):
        raise HTTPException(status_code=400, detail="The demo restaurant cannot be deleted")
    for collection in ("restaurant_settings", "menu_categories", "menu_items", "menu_addons", "orders",
                       "order_items", "order_status_history", "customers", "conversations", "messages",
                       "carts", "whatsapp_sessions", "whatsapp_logs", "google_sheet_connections",
                       "google_sync_jobs", "subscriptions", "subscription_payments", "client_credentials",
                       "admin_alerts", "users"):
        await db[collection].delete_many({"restaurant_id": restaurant_id})
    await db.restaurants.delete_one({"_id": oid(restaurant_id)})
    await audit(None, admin["email"], "admin.client.delete", {"name": restaurant["name"]})
    return {"ok": True}


@router.get("/alerts")
async def list_alerts(admin: dict = Depends(require_platform_admin), unread_only: bool = False, limit: int = Query(50, le=200)):
    query = {"read": False} if unread_only else {}
    rows = await db.admin_alerts.find(query).sort("created_at", -1).to_list(limit)
    return {
        "unread": await db.admin_alerts.count_documents({"read": False}),
        "alerts": [
            {"id": str(a["_id"]), "restaurant_id": a.get("restaurant_id"), "restaurant_name": a.get("restaurant_name"),
             "kind": a["kind"], "severity": a["severity"], "message": a["message"],
             "read": a.get("read", False), "created_at": a["created_at"]}
            for a in rows
        ],
    }


@router.post("/alerts/read")
async def mark_alerts_read(admin: dict = Depends(require_platform_admin), alert_id: Optional[str] = None):
    query = {"_id": oid(alert_id)} if alert_id else {"read": False}
    result = await db.admin_alerts.update_many(query, {"$set": {"read": True}})
    return {"updated": result.modified_count}


@router.post("/subscriptions/run-check")
async def run_check(admin: dict = Depends(require_platform_admin)):
    """Manually trigger the same sweep the daily cron runs."""
    result = await subscriptions.evaluate_all()
    await audit(None, admin["email"], "admin.subscription.manual_sweep", result)
    return {**result, "ran_at": datetime.now(timezone.utc)}
