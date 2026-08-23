import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.db import db, oid
from core.security import audit, get_current_user, tenant
from services import sheets
from services.whatsapp import get_whatsapp_provider

router = APIRouter(prefix="/api", tags=["channels"])


class SheetBody(BaseModel):
    spreadsheet_id: str
    spreadsheet_name: str | None = None


@router.get("/whatsapp/status")
async def whatsapp_status(restaurant_id: str = Depends(tenant)):
    provider = get_whatsapp_provider()
    session = await provider.get_status(restaurant_id)
    logs = await db.whatsapp_logs.find({"restaurant_id": restaurant_id}).sort("created_at", -1).to_list(30)
    return {
        "provider": provider.name,
        "provider_note": "Simulator provider: messages are delivered to the built-in WhatsApp simulator. "
                         "The Baileys provider is an UNOFFICIAL WhatsApp Web bridge and is not the official "
                         "WhatsApp Business API - enable it only with numbers you are authorised to use.",
        "session": session,
        "logs": [{"message": l["message"], "level": l.get("level", "info"), "created_at": l["created_at"]} for l in logs],
    }


@router.post("/whatsapp/qr")
async def whatsapp_qr(restaurant_id: str = Depends(tenant)):
    try:
        payload = await get_whatsapp_provider().get_qr_code(restaurant_id)
    except (RuntimeError, NotImplementedError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"qr_payload": payload}


@router.post("/whatsapp/connect")
async def whatsapp_connect(restaurant_id: str = Depends(tenant), user: dict = Depends(get_current_user)):
    try:
        session = await get_whatsapp_provider().connect(restaurant_id)
    except (RuntimeError, NotImplementedError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    await audit(restaurant_id, user["email"], "whatsapp.connect")
    session.pop("_id", None)
    return session


@router.post("/whatsapp/disconnect")
async def whatsapp_disconnect(restaurant_id: str = Depends(tenant), user: dict = Depends(get_current_user)):
    session = await get_whatsapp_provider().disconnect(restaurant_id)
    await audit(restaurant_id, user["email"], "whatsapp.disconnect")
    session.pop("_id", None)
    return session


@router.get("/google-sheets")
async def sheets_status(restaurant_id: str = Depends(tenant)):
    connection = await sheets.get_connection(restaurant_id)
    counts = await sheets.stats(restaurant_id)
    recent = await db.google_sync_jobs.find({"restaurant_id": restaurant_id}).sort("created_at", -1).to_list(25)
    return {
        "connection": connection,
        "counts": counts,
        "tabs": list(sheets.SHEET_TABS.keys()),
        "credentials_configured": bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()),
        "jobs": [
            {"id": str(j["_id"]), "event": j["event"], "sync_status": j["sync_status"],
             "sync_attempts": j.get("sync_attempts", 0), "error_message": j.get("error_message"),
             "created_at": j["created_at"], "last_attempt": j.get("last_attempt")}
            for j in recent
        ],
    }


@router.post("/google-sheets/connect")
async def sheets_connect(body: SheetBody, restaurant_id: str = Depends(tenant), user: dict = Depends(get_current_user)):
    if not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip():
        raise HTTPException(
            status_code=400,
            detail="Add your Google service account JSON to GOOGLE_SERVICE_ACCOUNT_JSON in backend/.env first, then share the sheet with that service account email.",
        )
    await sheets.get_connection(restaurant_id)
    await db.google_sheet_connections.update_one(
        {"restaurant_id": restaurant_id},
        {"$set": {"spreadsheet_id": body.spreadsheet_id, "spreadsheet_name": body.spreadsheet_name or "Restaurant Data",
                  "status": "connected", "last_error": None}},
    )
    await audit(restaurant_id, user["email"], "sheets.connect", {"spreadsheet_id": body.spreadsheet_id})
    return await sheets.get_connection(restaurant_id)


@router.post("/google-sheets/disconnect")
async def sheets_disconnect(restaurant_id: str = Depends(tenant)):
    await db.google_sheet_connections.update_one(
        {"restaurant_id": restaurant_id},
        {"$set": {"status": "not_connected", "spreadsheet_id": None, "spreadsheet_name": None}},
    )
    return await sheets.get_connection(restaurant_id)


@router.post("/google-sheets/sync")
async def sheets_sync_now(restaurant_id: str = Depends(tenant)):
    result = await sheets.drain(restaurant_id, limit=100)
    connection = await sheets.get_connection(restaurant_id)
    return {**result, "connection": connection, "counts": await sheets.stats(restaurant_id)}
