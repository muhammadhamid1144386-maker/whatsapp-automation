import os
from pathlib import Path
from typing import Annotated, Any, Optional

from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _coerce_object_id(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    return value


PyObjectId = Annotated[str, BeforeValidator(_coerce_object_id)]

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]


def oid(value: str) -> ObjectId:
    return ObjectId(value)


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    def to_mongo(self) -> dict:
        data = self.model_dump(by_alias=True)
        data.pop("_id", None)
        return data

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if doc is None:
            return None
        return cls.model_validate(doc)


async def ensure_indexes() -> None:
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.restaurants.create_index("slug", unique=True)
    await db.customers.create_index([("restaurant_id", 1), ("phone", 1)], unique=True)
    await db.conversations.create_index([("restaurant_id", 1), ("phone", 1)], unique=True)
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
    await db.menu_items.create_index([("restaurant_id", 1), ("category_id", 1)])
    await db.menu_categories.create_index([("restaurant_id", 1), ("sort_order", 1)])
    await db.orders.create_index([("restaurant_id", 1), ("created_at", -1)])
    await db.orders.create_index("order_number", unique=True)
    await db.orders.create_index("idempotency_key", unique=True, sparse=True)
    await db.order_items.create_index("order_id")
    await db.order_status_history.create_index([("order_id", 1), ("created_at", 1)])
    await db.processed_messages.create_index("external_id", unique=True)
    await db.google_sync_jobs.create_index([("restaurant_id", 1), ("sync_status", 1)])
    await db.carts.create_index("conversation_id", unique=True)
    await db.whatsapp_sessions.create_index("restaurant_id", unique=True)
    await db.subscriptions.create_index("restaurant_id", unique=True)
    await db.subscription_payments.create_index([("restaurant_id", 1), ("created_at", -1)])
    await db.client_credentials.create_index("restaurant_id", unique=True)
    await db.admin_alerts.create_index([("read", 1), ("created_at", -1)])
    await db.cron_runs.create_index("run_id", unique=True)


async def next_sequence(name: str, start: int = 1000) -> int:
    doc = await db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=True,
    )
    return start + int(doc["value"])
