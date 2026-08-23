"""Platform cron endpoints. Called by the scheduler defined in /app/.emergent/crons.yml."""

import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from core.db import db
from services import subscriptions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cron", tags=["cron"])


def _authorise(authorization: Optional[str]) -> None:
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not hmac.compare_digest(authorization[7:], secret):
        raise HTTPException(status_code=401, detail="Unauthorized")


async def _sweep(run_id: str) -> None:
    try:
        result = await subscriptions.evaluate_all()
        await db.cron_runs.update_one({"run_id": run_id}, {"$set": {"result": result, "finished_at": datetime.now(timezone.utc)}})
    except Exception as exc:
        logger.exception("subscription sweep failed: %s", exc)
        await db.cron_runs.update_one({"run_id": run_id}, {"$set": {"error": str(exc)[:400]}})


@router.post("/subscriptions")
async def subscription_sweep(
    request: Request,
    background: BackgroundTasks,
    authorization: Optional[str] = Header(default=None),
    x_webhook_id: Optional[str] = Header(default=None),
):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    _authorise(authorization)
    try:
        envelope = await request.json()
    except Exception:
        envelope = {}
    run_id = x_webhook_id or envelope.get("run_id") or f"manual:{datetime.now(timezone.utc).isoformat()}"

    existing = await db.cron_runs.find_one({"run_id": run_id})
    if existing:
        return {"accepted": True, "duplicate": True, "run_id": run_id}

    await db.cron_runs.insert_one(
        {"run_id": run_id, "job": "subscriptions", "received_at": datetime.now(timezone.utc), "result": None}
    )
    background.add_task(_sweep, run_id)
    return {"accepted": True, "run_id": run_id}
