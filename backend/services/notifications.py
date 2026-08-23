"""NotificationService: single outbound funnel for customer notifications.

MVP ships the WhatsApp channel only; SMS/email/push can be registered later
without touching order logic.
"""

import logging

from models import OrderStatus
from services.whatsapp import get_whatsapp_provider

logger = logging.getLogger(__name__)


def _money(value: float) -> str:
    return f"{value:,.0f}"


def order_placed_text(order: dict, restaurant: dict, lang: str) -> str:
    num = order["order_number"]
    eta = f"{order['eta_min']}-{order['eta_max']}"
    if order["order_type"] == "delivery":
        if lang == "ur":
            return f"آرڈر {num} کنفرم ہو گیا ہے۔ آپ کا آرڈر تقریباً {eta} منٹ میں ڈیلیور ہو جائے گا۔ کل رقم PKR {_money(order['total'])}۔"
        if lang == "roman_ur":
            return f"Order {num} confirm ho gaya hai. Aap ka order approximately {eta} minutes mein deliver ho jayega. Total PKR {_money(order['total'])}."
        return f"Order {num} has been placed. Estimated delivery in approximately {eta} minutes. Total PKR {_money(order['total'])}."
    if lang == "ur":
        return f"آرڈر {num} کنفرم ہو گیا ہے۔ تقریباً {eta} منٹ میں پک اپ کے لیے تیار ہو گا۔ کل رقم PKR {_money(order['total'])}۔"
    if lang == "roman_ur":
        return f"Order {num} confirm ho gaya hai. Aap ka order approximately {eta} minutes mein pickup ke liye ready hoga. Total PKR {_money(order['total'])}."
    return f"Order {num} has been placed. Ready for pickup in approximately {eta} minutes. Total PKR {_money(order['total'])}."


def status_text(order: dict, restaurant: dict, status: str, lang: str, reason: str | None = None) -> str | None:
    num = order["order_number"]
    eta = f"{order['eta_min']}-{order['eta_max']}"
    delivery = order["order_type"] == "delivery"
    name = restaurant.get("name", "the restaurant")

    if status == OrderStatus.CONFIRMED.value:
        if delivery:
            if lang == "ur":
                return f"زبردست! آپ کا آرڈر {num} کنفرم ہو گیا ہے اور تقریباً {eta} منٹ میں پہنچ جائے گا۔"
            if lang == "roman_ur":
                return f"Great! Aap ka order {num} confirm ho gaya hai. Approximately {eta} minutes mein pohanch jayega."
            return f"Your order {num} has been confirmed and is expected to arrive in approximately {eta} minutes."
        if lang == "ur":
            return f"آپ کا آرڈر {num} کنفرم ہو گیا ہے۔ تقریباً {eta} منٹ میں پک اپ کے لیے تیار ہو گا۔"
        if lang == "roman_ur":
            return f"Aap ka order {num} confirm ho gaya hai. Approximately {eta} minutes mein pickup ke liye ready hoga."
        return f"Your order {num} has been confirmed. It will be ready for pickup in approximately {eta} minutes."

    if status == OrderStatus.PREPARING.value:
        if lang == "ur":
            return f"آپ کا آرڈر {num} تیار کیا جا رہا ہے۔"
        if lang == "roman_ur":
            return f"Aap ka order {num} ab tayyar kiya ja raha hai."
        return f"Your order {num} is now being prepared."

    if status == OrderStatus.READY.value:
        if lang == "ur":
            return f"آپ کا آرڈر {num} تیار ہے۔"
        if lang == "roman_ur":
            return f"Aap ka order {num} ready hai."
        return f"Your order {num} is ready."

    if status == OrderStatus.OUT_FOR_DELIVERY.value:
        if lang == "ur":
            return f"آپ کا آرڈر {num} راستے میں ہے۔"
        if lang == "roman_ur":
            return f"Aap ka order {num} raaste mein hai."
        return f"Your order {num} is on the way."

    if status == OrderStatus.DELIVERED.value:
        if lang == "ur":
            return f"آپ کا آرڈر {num} ڈیلیور ہو گیا ہے۔ {name} سے آرڈر کرنے کا شکریہ!"
        if lang == "roman_ur":
            return f"Aap ka order {num} deliver ho gaya hai. {name} se order karne ka shukriya!"
        return f"Your order {num} has been delivered. Thank you for ordering from {name}!"

    if status == OrderStatus.REJECTED.value:
        detail = f" Reason: {reason}." if reason else ""
        if lang == "ur":
            return f"معذرت، آپ کا آرڈر {num} فی الحال قبول نہیں ہو سکا۔{detail} مدد کے لیے {name} سے رابطہ کریں۔"
        if lang == "roman_ur":
            return f"Sorry, aap ka order {num} filhaal accept nahi ho saka.{detail} Madad ke liye {name} se rabta karein."
        return f"Unfortunately your order {num} could not be accepted.{detail} Please contact {name} if you need assistance."

    if status == OrderStatus.CANCELLED.value:
        detail = f" Reason: {reason}." if reason else ""
        if lang == "roman_ur":
            return f"Aap ka order {num} cancel kar diya gaya hai.{detail} Madad ke liye {name} se rabta karein."
        return f"Unfortunately your order {num} has been cancelled.{detail} Please contact {name} if you need assistance."

    return None


class NotificationService:
    def __init__(self) -> None:
        self.channels = {"whatsapp": get_whatsapp_provider()}

    async def notify_customer(self, restaurant_id: str, phone: str, text: str) -> bool:
        try:
            return await self.channels["whatsapp"].send_message(restaurant_id, phone, text)
        except Exception as exc:  # a broken transport must never break order flow
            logger.exception("notification failed: %s", exc)
            return False


notifications = NotificationService()
