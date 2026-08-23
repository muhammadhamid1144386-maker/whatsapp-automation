"""Subscription lifecycle for platform clients.

Statuses: active → grace (past due, inside grace window) → blocked (grace exhausted).
Recording a payment always returns a subscription to `active` and clears sent reminders.
"""

import calendar
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.db import db, oid

logger = logging.getLogger(__name__)

PERIOD_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}
REMINDER_DAYS = (7, 3, 1)
DEFAULT_GRACE_DAYS = 7


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def add_period(start: datetime, period: str) -> datetime:
    months = PERIOD_MONTHS.get(period, 1)
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


async def get_or_create(restaurant_id: str, *, amount: float = 0, period: str = "monthly") -> dict:
    sub = await db.subscriptions.find_one({"restaurant_id": restaurant_id})
    if sub:
        return sub
    now = datetime.now(timezone.utc)
    doc = {
        "restaurant_id": restaurant_id,
        "plan_name": "Standard",
        "amount": float(amount),
        "currency": "PKR",
        "billing_period": period if period in PERIOD_MONTHS else "monthly",
        "grace_days": DEFAULT_GRACE_DAYS,
        "started_at": now,
        "current_period_start": now,
        "current_period_end": add_period(now, period if period in PERIOD_MONTHS else "monthly"),
        "status": "active",
        "reminders_sent": [],
        "last_payment_at": None,
        "total_collected": 0.0,
        "updated_at": now,
    }
    result = await db.subscriptions.insert_one(dict(doc))
    doc["_id"] = result.inserted_id
    return doc


def summarise(sub: dict) -> dict:
    now = datetime.now(timezone.utc)
    end = _as_utc(sub.get("current_period_end")) or now
    seconds_left = (end - now).total_seconds()
    days_left = int(seconds_left // 86400) if seconds_left >= 0 else -int((-seconds_left) // 86400 + 1)
    grace_days = int(sub.get("grace_days", DEFAULT_GRACE_DAYS))
    return {
        "id": str(sub.get("_id", "")),
        "restaurant_id": sub.get("restaurant_id"),
        "plan_name": sub.get("plan_name", "Standard"),
        "amount": sub.get("amount", 0),
        "currency": sub.get("currency", "PKR"),
        "billing_period": sub.get("billing_period", "monthly"),
        "grace_days": grace_days,
        "started_at": sub.get("started_at"),
        "current_period_start": sub.get("current_period_start"),
        "current_period_end": sub.get("current_period_end"),
        "status": sub.get("status", "active"),
        "days_left": days_left,
        "grace_ends_at": end + timedelta(days=grace_days),
        "last_payment_at": sub.get("last_payment_at"),
        "total_collected": sub.get("total_collected", 0),
        "reminders_sent": sub.get("reminders_sent", []),
    }


async def alert(restaurant_id: str, restaurant_name: str, kind: str, severity: str, message: str) -> None:
    await db.admin_alerts.insert_one(
        {
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant_name,
            "kind": kind,
            "severity": severity,
            "message": message,
            "read": False,
            "created_at": datetime.now(timezone.utc),
        }
    )


async def update_plan(restaurant_id: str, **fields) -> dict:
    await get_or_create(restaurant_id)
    updates = {}
    if fields.get("plan_name"):
        updates["plan_name"] = fields["plan_name"]
    if fields.get("amount") is not None:
        updates["amount"] = float(fields["amount"])
    if fields.get("billing_period") in PERIOD_MONTHS:
        updates["billing_period"] = fields["billing_period"]
    if fields.get("grace_days") is not None:
        updates["grace_days"] = max(0, int(fields["grace_days"]))
    if fields.get("current_period_end"):
        end = fields["current_period_end"]
        updates["current_period_end"] = end if isinstance(end, datetime) else datetime.fromisoformat(str(end))
        updates["reminders_sent"] = []
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        await db.subscriptions.update_one({"restaurant_id": restaurant_id}, {"$set": updates})
    return summarise(await db.subscriptions.find_one({"restaurant_id": restaurant_id}))


async def record_payment(restaurant_id: str, amount: float, method: str = "Cash", note: str = "", recorded_by: str = "") -> dict:
    sub = await get_or_create(restaurant_id)
    now = datetime.now(timezone.utc)
    end = _as_utc(sub.get("current_period_end")) or now
    # Paying early extends the existing period; paying late starts a fresh one from today.
    base = end if end > now else now
    new_end = add_period(base, sub.get("billing_period", "monthly"))

    await db.subscriptions.update_one(
        {"restaurant_id": restaurant_id},
        {
            "$set": {
                "status": "active",
                "current_period_start": base,
                "current_period_end": new_end,
                "reminders_sent": [],
                "last_payment_at": now,
                "updated_at": now,
            },
            "$inc": {"total_collected": float(amount or 0)},
        },
    )
    await db.subscription_payments.insert_one(
        {
            "restaurant_id": restaurant_id,
            "amount": float(amount or 0),
            "currency": "PKR",
            "method": method or "Cash",
            "note": note or "",
            "recorded_by": recorded_by,
            "period_start": base,
            "period_end": new_end,
            "created_at": now,
        }
    )
    restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
    name = (restaurant or {}).get("name", "Client")
    await alert(restaurant_id, name, "payment_received", "success",
                f"Payment of PKR {float(amount or 0):,.0f} received from {name}. Subscription active until {new_end.date()}.")
    return summarise(await db.subscriptions.find_one({"restaurant_id": restaurant_id}))


async def set_status(restaurant_id: str, status: str, actor: str = "") -> dict:
    await get_or_create(restaurant_id)
    await db.subscriptions.update_one(
        {"restaurant_id": restaurant_id},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
    )
    restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
    name = (restaurant or {}).get("name", "Client")
    if status == "blocked":
        await alert(restaurant_id, name, "blocked", "critical", f"{name} has been blocked. Their dashboard login is now refused.")
    elif status == "active":
        await alert(restaurant_id, name, "unblocked", "success", f"{name} has been reactivated and can log in again.")
    return summarise(await db.subscriptions.find_one({"restaurant_id": restaurant_id}))


async def evaluate_all() -> dict:
    """Daily sweep: sends reminders, moves past-due clients into grace, then blocks them."""
    now = datetime.now(timezone.utc)
    subs = await db.subscriptions.find({"status": {"$in": ["active", "grace"]}}).to_list(1000)
    reminded = moved_to_grace = blocked = 0

    for sub in subs:
        restaurant_id = sub["restaurant_id"]
        restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
        if not restaurant:
            continue
        name = restaurant.get("name", "Client")
        end = _as_utc(sub.get("current_period_end")) or now
        grace_days = int(sub.get("grace_days", DEFAULT_GRACE_DAYS))
        sent = list(sub.get("reminders_sent", []))
        amount = float(sub.get("amount", 0) or 0)

        if now <= end:
            days_left = int((end - now).total_seconds() // 86400)
            for day in REMINDER_DAYS:
                tag = f"d{day}"
                if days_left <= day and tag not in sent:
                    sent.append(tag)
                    reminded += 1
                    await alert(
                        restaurant_id, name, "expiring", "warning",
                        f"{name}'s subscription expires in {max(days_left, 0)} day(s) on {end.date()}. "
                        f"Remind them to pay PKR {amount:,.0f}.",
                    )
                    break
            if sent != sub.get("reminders_sent", []):
                await db.subscriptions.update_one({"_id": sub["_id"]}, {"$set": {"reminders_sent": sent, "updated_at": now}})
            continue

        overdue_days = int((now - end).total_seconds() // 86400)
        if overdue_days < grace_days:
            if sub.get("status") != "grace" or "grace" not in sent:
                sent.append("grace") if "grace" not in sent else None
                moved_to_grace += 1
                await alert(
                    restaurant_id, name, "overdue", "warning",
                    f"{name}'s subscription expired on {end.date()}. {grace_days - overdue_days} grace day(s) left "
                    f"before automatic blocking. Payment due: PKR {amount:,.0f}.",
                )
            await db.subscriptions.update_one(
                {"_id": sub["_id"]}, {"$set": {"status": "grace", "reminders_sent": sent, "updated_at": now}}
            )
        else:
            if "blocked" not in sent:
                sent.append("blocked")
                blocked += 1
                await alert(
                    restaurant_id, name, "blocked", "critical",
                    f"{name} has been blocked automatically — payment of PKR {amount:,.0f} was not received "
                    f"within the {grace_days}-day grace period.",
                )
            await db.subscriptions.update_one(
                {"_id": sub["_id"]}, {"$set": {"status": "blocked", "reminders_sent": sent, "updated_at": now}}
            )

    result = {"checked": len(subs), "reminded": reminded, "moved_to_grace": moved_to_grace, "blocked": blocked}
    logger.info("subscription sweep %s", result)
    return result


async def is_blocked(restaurant_id: str) -> bool:
    sub = await db.subscriptions.find_one({"restaurant_id": restaurant_id}, {"status": 1})
    return bool(sub) and sub.get("status") == "blocked"
