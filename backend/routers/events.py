import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from core.db import db
from core.security import tenant
from services.realtime import broker, customer_channel, dashboard_channel, sse_format

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["realtime"])

SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}


async def _stream(request: Request, channel: str):
    queue = broker.subscribe(channel)
    try:
        yield sse_format({"event": "CONNECTED", "data": {"channel": channel}})
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=20)
                yield sse_format(payload)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
    finally:
        broker.unsubscribe(channel, queue)


@router.get("/events/stream")
async def dashboard_stream(request: Request, restaurant_id: str = Depends(tenant)):
    return StreamingResponse(_stream(request, dashboard_channel(restaurant_id)), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/chat/{slug}/stream")
async def customer_stream(slug: str, phone: str, request: Request):
    restaurant = await db.restaurants.find_one({"slug": slug})
    if not restaurant:
        return StreamingResponse(iter([sse_format({"event": "ERROR", "data": "unknown restaurant"})]), media_type="text/event-stream", headers=SSE_HEADERS)
    channel = customer_channel(str(restaurant["_id"]), phone)
    return StreamingResponse(_stream(request, channel), media_type="text/event-stream", headers=SSE_HEADERS)
