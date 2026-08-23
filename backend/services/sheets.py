"""Google Sheets synchronisation.

PostgreSQL/Mongo is the source of truth. Sheets receives asynchronous copies via a
job queue so a Sheets outage can never fail or delay an order.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from core.db import db, oid
from models import SyncStatus

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5

SHEET_TABS = {
    "Orders": [
        "Order ID", "Restaurant ID", "Restaurant", "Customer Name", "Phone", "Order Type",
        "Items", "Subtotal", "Delivery Fee", "Discount", "Total", "Address", "Payment Method",
        "Status", "Created At", "Updated At",
    ],
    "Customers": ["Customer ID", "Name", "Phone", "Total Orders", "Total Spent", "Last Order", "Created At"],
    "Order Items": ["Order ID", "Item", "Unit Price", "Quantity", "Line Total"],
    "Messages": ["Conversation ID", "Phone", "Sender", "Message", "Created At"],
    "Daily Summary": ["Date", "Orders", "Sales", "Average Order Value", "Completed", "Cancelled"],
}


def _credentials_available() -> bool:
    return bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip())


def _open_spreadsheet(spreadsheet_id: str):
    import gspread
    from google.oauth2.service_account import Credentials

    raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"].strip()
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    )
    return gspread.authorize(creds).open_by_key(spreadsheet_id)


async def get_connection(restaurant_id: str) -> dict:
    doc = await db.google_sheet_connections.find_one({"restaurant_id": restaurant_id})
    if not doc:
        doc = {
            "restaurant_id": restaurant_id,
            "status": "not_connected",
            "spreadsheet_id": os.environ.get("GOOGLE_SHEET_ID") or None,
            "spreadsheet_name": None,
            "service_account_email": None,
            "last_sync_at": None,
            "last_error": None,
            "updated_at": datetime.now(timezone.utc),
        }
        result = await db.google_sheet_connections.insert_one(dict(doc))
        doc["_id"] = result.inserted_id
    doc["id"] = str(doc.pop("_id"))
    doc["credentials_configured"] = _credentials_available()
    return doc


async def queue_sync(restaurant_id: str, event: str, entity_id: Optional[str], payload: dict) -> str:
    result = await db.google_sync_jobs.insert_one(
        {
            "restaurant_id": restaurant_id,
            "event": event,
            "entity_id": entity_id,
            "payload": payload,
            "sync_status": SyncStatus.PENDING.value,
            "sync_attempts": 0,
            "last_attempt": None,
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return str(result.inserted_id)


def _rows_for(job: dict) -> tuple[str, list[list]]:
    payload = job.get("payload", {})
    event = job["event"]
    if event in ("ORDER_CREATED", "ORDER_UPDATED", "ORDER_STATUS_CHANGED"):
        return "Orders", [[
            payload.get("order_number", ""), job.get("restaurant_id", ""), payload.get("restaurant_name", ""),
            payload.get("customer_name", ""), payload.get("customer_phone", ""), payload.get("order_type", ""),
            payload.get("items_text", ""), payload.get("subtotal", 0), payload.get("delivery_fee", 0),
            payload.get("discount", 0), payload.get("total", 0), payload.get("address", ""),
            payload.get("payment_method", ""), payload.get("status", ""),
            payload.get("created_at", ""), payload.get("updated_at", ""),
        ]]
    if event in ("CUSTOMER_CREATED", "CUSTOMER_UPDATED"):
        return "Customers", [[
            payload.get("customer_id", ""), payload.get("name", ""), payload.get("phone", ""),
            payload.get("total_orders", 0), payload.get("total_spent", 0),
            payload.get("last_order", ""), payload.get("created_at", ""),
        ]]
    if event == "ORDER_ITEMS":
        return "Order Items", [
            [payload.get("order_number", ""), i.get("name"), i.get("unit_price"), i.get("quantity"), i.get("line_total")]
            for i in payload.get("items", [])
        ]
    return "Messages", [[
        payload.get("conversation_id", ""), payload.get("phone", ""),
        payload.get("sender", ""), payload.get("body", ""), payload.get("created_at", ""),
    ]]


def _push_rows_blocking(spreadsheet_id: str, tab: str, rows: list[list]) -> None:
    spreadsheet = _open_spreadsheet(spreadsheet_id)
    try:
        worksheet = spreadsheet.worksheet(tab)
    except Exception:
        worksheet = spreadsheet.add_worksheet(title=tab, rows=1000, cols=max(len(SHEET_TABS.get(tab, [])), 10))
        worksheet.append_row(SHEET_TABS.get(tab, []))
    for row in rows:
        worksheet.append_row([("" if v is None else v) for v in row], value_input_option="USER_ENTERED")


async def run_job(job: dict) -> bool:
    restaurant_id = job["restaurant_id"]
    connection = await get_connection(restaurant_id)
    now = datetime.now(timezone.utc)
    attempts = job.get("sync_attempts", 0) + 1

    async def fail(message: str) -> bool:
        status = SyncStatus.FAILED.value if attempts >= MAX_ATTEMPTS else SyncStatus.PENDING.value
        await db.google_sync_jobs.update_one(
            {"_id": job["_id"]},
            {"$set": {"sync_status": status, "sync_attempts": attempts, "last_attempt": now, "error_message": message}},
        )
        await db.google_sheet_connections.update_one({"restaurant_id": restaurant_id}, {"$set": {"last_error": message}})
        if job.get("entity_id") and job["event"].startswith("ORDER"):
            await db.orders.update_one({"_id": oid(job["entity_id"])}, {"$set": {"google_sync_status": status}})
        return False

    if not _credentials_available():
        return await fail("Google Sheets is not connected (missing service account credentials).")
    if not connection.get("spreadsheet_id"):
        return await fail("No spreadsheet configured for this restaurant.")

    tab, rows = _rows_for(job)
    if not rows:
        await db.google_sync_jobs.update_one(
            {"_id": job["_id"]}, {"$set": {"sync_status": SyncStatus.SYNCED.value, "last_attempt": now}}
        )
        return True
    try:
        await asyncio.to_thread(_push_rows_blocking, connection["spreadsheet_id"], tab, rows)
    except Exception as exc:
        return await fail(str(exc)[:400])

    await db.google_sync_jobs.update_one(
        {"_id": job["_id"]},
        {"$set": {"sync_status": SyncStatus.SYNCED.value, "sync_attempts": attempts, "last_attempt": now, "error_message": None}},
    )
    await db.google_sheet_connections.update_one(
        {"restaurant_id": restaurant_id}, {"$set": {"last_sync_at": now, "last_error": None, "status": "connected"}}
    )
    if job.get("entity_id") and job["event"].startswith("ORDER"):
        await db.orders.update_one(
            {"_id": oid(job["entity_id"])},
            {"$set": {"google_sync_status": SyncStatus.SYNCED.value, "google_synced_at": now}},
        )
    return True


async def drain(restaurant_id: Optional[str] = None, limit: int = 50) -> dict:
    query: dict = {"sync_status": SyncStatus.PENDING.value}
    if restaurant_id:
        query["restaurant_id"] = restaurant_id
    jobs = await db.google_sync_jobs.find(query).sort("created_at", 1).to_list(limit)
    synced = failed = 0
    for job in jobs:
        if await run_job(job):
            synced += 1
        else:
            failed += 1
    return {"processed": len(jobs), "synced": synced, "failed": failed}


async def sync_worker() -> None:
    while True:
        try:
            if _credentials_available():
                await drain(limit=25)
        except Exception as exc:
            logger.exception("sheets worker error: %s", exc)
        await asyncio.sleep(30)


async def stats(restaurant_id: str) -> dict:
    pipeline = [
        {"$match": {"restaurant_id": restaurant_id}},
        {"$group": {"_id": "$sync_status", "count": {"$sum": 1}}},
    ]
    rows = await db.google_sync_jobs.aggregate(pipeline).to_list(20)
    counts = {r["_id"]: r["count"] for r in rows}
    return {
        "pending": counts.get(SyncStatus.PENDING.value, 0),
        "synced": counts.get(SyncStatus.SYNCED.value, 0),
        "failed": counts.get(SyncStatus.FAILED.value, 0),
    }
