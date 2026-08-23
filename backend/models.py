from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from core.db import BaseDocument, PyObjectId


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderStatus(str, Enum):
    NEW = "NEW"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY = "READY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


STATUS_EVENT = {
    OrderStatus.NEW: "NEW_ORDER",
    OrderStatus.CONFIRMED: "ORDER_CONFIRMED",
    OrderStatus.PREPARING: "ORDER_PREPARING",
    OrderStatus.READY: "ORDER_READY",
    OrderStatus.OUT_FOR_DELIVERY: "ORDER_OUT_FOR_DELIVERY",
    OrderStatus.DELIVERED: "ORDER_DELIVERED",
    OrderStatus.REJECTED: "ORDER_REJECTED",
    OrderStatus.CANCELLED: "ORDER_CANCELLED",
}


class ConversationState(str, Enum):
    GREETING = "GREETING"
    BROWSING_MENU = "BROWSING_MENU"
    SELECTING_ITEMS = "SELECTING_ITEMS"
    CART_REVIEW = "CART_REVIEW"
    COLLECTING_ORDER_TYPE = "COLLECTING_ORDER_TYPE"
    COLLECTING_NAME = "COLLECTING_NAME"
    COLLECTING_ADDRESS = "COLLECTING_ADDRESS"
    CONFIRMING_ORDER = "CONFIRMING_ORDER"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_STATUS = "ORDER_STATUS"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"


class SyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


class OpeningHour(BaseModel):
    day: int
    open: str = "11:00"
    close: str = "23:30"
    closed: bool = False


class Restaurant(BaseDocument):
    name: str
    slug: str
    logo_url: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    currency: str = "PKR"
    ai_greeting: Optional[str] = None
    business_rules: Optional[str] = None
    demo: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class RestaurantSettings(BaseDocument):
    restaurant_id: PyObjectId
    opening_hours: List[OpeningHour] = Field(default_factory=list)
    delivery_areas: List[str] = Field(default_factory=list)
    delivery_fee: float = 150
    min_order: float = 500
    prep_time_min: int = 20
    prep_time_max: int = 30
    delivery_time_min: int = 15
    delivery_time_max: int = 20
    allow_orders_when_closed: bool = False
    upsell_enabled: bool = True
    ai_active: bool = True
    timezone: str = "Asia/Karachi"


class User(BaseDocument):
    email: str
    password_hash: str
    name: str
    role: str = "owner"
    restaurant_id: Optional[PyObjectId] = None
    created_at: datetime = Field(default_factory=utcnow)


class Customer(BaseDocument):
    restaurant_id: PyObjectId
    name: Optional[str] = None
    phone: str
    total_orders: int = 0
    total_spent: float = 0
    last_order_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


class Conversation(BaseDocument):
    restaurant_id: PyObjectId
    customer_id: Optional[PyObjectId] = None
    phone: str
    state: str = ConversationState.GREETING.value
    language: str = "en"
    ai_active: bool = True
    last_message_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class Message(BaseDocument):
    conversation_id: PyObjectId
    restaurant_id: PyObjectId
    sender: str  # customer | ai | staff | system
    body: str
    message_type: str = "text"
    external_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class MenuCategory(BaseDocument):
    restaurant_id: PyObjectId
    name: str
    sort_order: int = 0
    active: bool = True


class MenuItem(BaseDocument):
    restaurant_id: PyObjectId
    category_id: PyObjectId
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    available: bool = True
    addon_ids: List[str] = Field(default_factory=list)
    sort_order: int = 0


class MenuAddon(BaseDocument):
    restaurant_id: PyObjectId
    name: str
    price: float
    available: bool = True


class CartLine(BaseModel):
    item_id: str
    name: str
    unit_price: float
    quantity: int = 1


class Cart(BaseDocument):
    restaurant_id: PyObjectId
    conversation_id: PyObjectId
    items: List[CartLine] = Field(default_factory=list)
    order_type: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    address: Optional[str] = None
    payment_method: str = "Cash"
    upsell_offered: List[str] = Field(default_factory=list)
    upsell_declined: bool = False
    updated_at: datetime = Field(default_factory=utcnow)


class OrderLine(BaseModel):
    item_id: str
    name: str
    unit_price: float
    quantity: int
    line_total: float


class Order(BaseDocument):
    restaurant_id: PyObjectId
    order_number: str
    conversation_id: Optional[PyObjectId] = None
    customer_id: Optional[PyObjectId] = None
    customer_name: str
    customer_phone: str
    order_type: str = "delivery"
    items: List[OrderLine] = Field(default_factory=list)
    subtotal: float = 0
    delivery_fee: float = 0
    discount: float = 0
    total: float = 0
    address: Optional[str] = None
    payment_method: str = "Cash"
    status: str = OrderStatus.NEW.value
    eta_min: int = 0
    eta_max: int = 0
    language: str = "en"
    reject_reason: Optional[str] = None
    google_sync_status: str = SyncStatus.PENDING.value
    google_synced_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OrderItemRow(BaseDocument):
    order_id: PyObjectId
    restaurant_id: PyObjectId
    item_id: str
    name: str
    unit_price: float
    quantity: int
    line_total: float


class OrderStatusHistory(BaseDocument):
    order_id: PyObjectId
    restaurant_id: PyObjectId
    old_status: Optional[str] = None
    new_status: str
    changed_by: str = "system"
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class WhatsAppSession(BaseDocument):
    restaurant_id: PyObjectId
    provider: str = "simulator"
    status: str = "disconnected"
    connected_number: Optional[str] = None
    qr_payload: Optional[str] = None
    last_connected_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=utcnow)


class WhatsAppLog(BaseDocument):
    restaurant_id: PyObjectId
    level: str = "info"
    message: str
    created_at: datetime = Field(default_factory=utcnow)


class GoogleSheetConnection(BaseDocument):
    restaurant_id: PyObjectId
    status: str = "not_connected"
    spreadsheet_id: Optional[str] = None
    spreadsheet_name: Optional[str] = None
    service_account_email: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    updated_at: datetime = Field(default_factory=utcnow)


class GoogleSyncJob(BaseDocument):
    restaurant_id: PyObjectId
    event: str
    entity_id: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    sync_status: str = SyncStatus.PENDING.value
    sync_attempts: int = 0
    last_attempt: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
