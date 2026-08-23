import asyncio
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class EventBroker:
    """In-process pub/sub used to drive Server-Sent Events to dashboards and chat clients."""

    def __init__(self) -> None:
        self._channels: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, channel: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._channels.setdefault(channel, set()).add(queue)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue) -> None:
        subs = self._channels.get(channel)
        if not subs:
            return
        subs.discard(queue)
        if not subs:
            self._channels.pop(channel, None)

    def listeners(self, channel: str) -> int:
        return len(self._channels.get(channel, ()))

    async def publish(self, channel: str, event: str, data: Any) -> None:
        payload = {"event": event, "data": data, "ts": datetime.utcnow().isoformat()}
        for queue in list(self._channels.get(channel, ())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("dropping realtime event for saturated channel %s", channel)


broker = EventBroker()


def dashboard_channel(restaurant_id: str) -> str:
    return f"dashboard:{restaurant_id}"


def customer_channel(restaurant_id: str, phone: str) -> str:
    return f"customer:{restaurant_id}:{phone}"


def sse_format(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"
