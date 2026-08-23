"""WhatsApp transport layer.

Business logic must only ever talk to `WhatsAppProvider`. Swapping in the official
WhatsApp Business API later means adding a provider class here and nothing else.

    WhatsAppProvider
      |-- SimulatorProvider          (built-in, used for demo/local development)
      |-- BaileysProvider            (unofficial WhatsApp Web bridge, opt-in)
      |-- OfficialWhatsAppProvider   (future: Meta Cloud API)
"""

import logging
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from core.db import db, oid
from services.realtime import broker, customer_channel, dashboard_channel

logger = logging.getLogger(__name__)


class WhatsAppProvider(ABC):
    name = "abstract"

    @abstractmethod
    async def connect(self, restaurant_id: str) -> dict: ...

    @abstractmethod
    async def disconnect(self, restaurant_id: str) -> dict: ...

    @abstractmethod
    async def get_status(self, restaurant_id: str) -> dict: ...

    @abstractmethod
    async def get_qr_code(self, restaurant_id: str) -> Optional[str]: ...

    @abstractmethod
    async def send_message(self, restaurant_id: str, to: str, text: str) -> bool: ...

    async def send_image(self, restaurant_id: str, to: str, url: str, caption: str = "") -> bool:
        return await self.send_message(restaurant_id, to, f"{caption}\n{url}".strip())

    async def send_document(self, restaurant_id: str, to: str, url: str, caption: str = "") -> bool:
        return await self.send_message(restaurant_id, to, f"{caption}\n{url}".strip())


async def _log(restaurant_id: str, message: str, level: str = "info") -> None:
    await db.whatsapp_logs.insert_one(
        {
            "restaurant_id": restaurant_id,
            "level": level,
            "message": message,
            "created_at": datetime.now(timezone.utc),
        }
    )
    await broker.publish(dashboard_channel(restaurant_id), "WHATSAPP_LOG", {"message": message, "level": level})


async def _session(restaurant_id: str) -> dict:
    doc = await db.whatsapp_sessions.find_one({"restaurant_id": restaurant_id})
    if not doc:
        doc = {
            "restaurant_id": restaurant_id,
            "provider": os.environ.get("WHATSAPP_PROVIDER", "simulator"),
            "status": "disconnected",
            "connected_number": None,
            "qr_payload": None,
            "last_connected_at": None,
            "updated_at": datetime.now(timezone.utc),
        }
        result = await db.whatsapp_sessions.insert_one(dict(doc))
        doc["_id"] = result.inserted_id
    return doc


async def _set_session(restaurant_id: str, **fields) -> dict:
    fields["updated_at"] = datetime.now(timezone.utc)
    await _session(restaurant_id)
    await db.whatsapp_sessions.update_one({"restaurant_id": restaurant_id}, {"$set": fields})
    doc = await db.whatsapp_sessions.find_one({"restaurant_id": restaurant_id})
    doc["id"] = str(doc.pop("_id"))
    await broker.publish(dashboard_channel(restaurant_id), "WHATSAPP_STATUS", doc)
    return doc


class SimulatorProvider(WhatsAppProvider):
    """Delivers messages into the in-app WhatsApp simulator over SSE.

    No third-party WhatsApp account is touched. Every outbound message is persisted
    as a real conversation message so the transcript matches production behaviour.
    """

    name = "simulator"

    async def connect(self, restaurant_id: str) -> dict:
        restaurant = await db.restaurants.find_one({"_id": oid(restaurant_id)})
        session = await _set_session(
            restaurant_id,
            status="connected",
            connected_number=(restaurant or {}).get("whatsapp_number") or "+92 300 0000000",
            qr_payload=None,
            last_connected_at=datetime.now(timezone.utc),
        )
        await _log(restaurant_id, "WhatsApp simulator connected")
        return session

    async def disconnect(self, restaurant_id: str) -> dict:
        session = await _set_session(restaurant_id, status="disconnected", connected_number=None, qr_payload=None)
        await _log(restaurant_id, "WhatsApp session disconnected", "warn")
        return session

    async def get_status(self, restaurant_id: str) -> dict:
        session = await _session(restaurant_id)
        session["id"] = str(session.pop("_id", ""))
        return session

    async def get_qr_code(self, restaurant_id: str) -> Optional[str]:
        session = await _set_session(restaurant_id, status="connecting", qr_payload=f"wa-sim:{uuid.uuid4().hex[:18]}")
        return session.get("qr_payload")

    async def send_message(self, restaurant_id: str, to: str, text: str) -> bool:
        session = await _session(restaurant_id)
        if session.get("status") == "disconnected":
            await _log(restaurant_id, f"Outbound message to {to} queued - channel not connected", "warn")
        conversation = await db.conversations.find_one({"restaurant_id": restaurant_id, "phone": to})
        if conversation:
            await db.messages.insert_one(
                {
                    "conversation_id": str(conversation["_id"]),
                    "restaurant_id": restaurant_id,
                    "sender": "ai",
                    "body": text,
                    "message_type": "notification",
                    "external_id": None,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            await broker.publish(
                dashboard_channel(restaurant_id),
                "NEW_MESSAGE",
                {"conversation_id": str(conversation["_id"]), "sender": "ai", "body": text},
            )
        await broker.publish(customer_channel(restaurant_id, to), "WHATSAPP_MESSAGE", {"body": text, "sender": "ai"})
        return True


class BaileysProvider(WhatsAppProvider):
    """Unofficial WhatsApp Web bridge (Baileys / whatsapp-web.js).

    NOT the official WhatsApp Business API. Requires a separate long-running Node
    sidecar reachable at BAILEYS_BRIDGE_URL that exposes /connect, /status, /qr,
    /send and /disconnect. Disabled unless that URL is configured.
    """

    name = "baileys"

    def __init__(self) -> None:
        self.bridge_url = os.environ.get("BAILEYS_BRIDGE_URL", "").rstrip("/")

    def _guard(self) -> None:
        if not self.bridge_url:
            raise RuntimeError(
                "Baileys bridge is not configured. Set BAILEYS_BRIDGE_URL to the Node "
                "sidecar running @whiskeysockets/baileys, or keep WHATSAPP_PROVIDER=simulator."
            )

    async def connect(self, restaurant_id: str) -> dict:
        self._guard()
        raise NotImplementedError

    async def disconnect(self, restaurant_id: str) -> dict:
        self._guard()
        raise NotImplementedError

    async def get_status(self, restaurant_id: str) -> dict:
        self._guard()
        raise NotImplementedError

    async def get_qr_code(self, restaurant_id: str) -> Optional[str]:
        self._guard()
        raise NotImplementedError

    async def send_message(self, restaurant_id: str, to: str, text: str) -> bool:
        self._guard()
        raise NotImplementedError


_providers: dict[str, WhatsAppProvider] = {}


def get_whatsapp_provider() -> WhatsAppProvider:
    key = os.environ.get("WHATSAPP_PROVIDER", "simulator").lower()
    if key not in _providers:
        _providers[key] = BaileysProvider() if key == "baileys" else SimulatorProvider()
    return _providers[key]
