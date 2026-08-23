"""
Closed-hours behaviour tests for the AI Restaurant Assistant.

Covers:
  * is_open() unit tests (past-midnight, prev-day rollover, next-opening lookup)
  * Closed-hours chat gate: no AI/LLM ordering during closed hours
  * Localised closed messages (en / roman_ur / ur)
  * Pre-order override toggle
  * Language detection fixes (menu dikhayen / Yes place my order etc.)
  * Public /api/chat/{slug} exposes open_now and opens_at

Restores Pizza Palace to open 11:00-23:59 all 7 days at the end (session-scoped fixture).
"""
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests

# Ensure /app/backend is importable so we can unit-test is_open() directly.
sys.path.insert(0, "/app/backend")

from services.orders import is_open  # noqa: E402
from services.ai import detect_language  # noqa: E402

# All tests in this module share Pizza Palace settings. Force them into
# a single xdist worker so parallel executions don't stomp on each other.
pytestmark = pytest.mark.xdist_group("closed_hours_shared_settings")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://whatsapp-order-saas.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
SLUG = "pizza-palace"

OWNER = {"email": "owner@pizzapalace.pk", "password": "Pizza123!"}
AI_TIMEOUT = 90


# ------------------------- helpers -------------------------
def _week_open(open_time="11:00", close_time="23:59", closed=False):
    return [{"day": d, "open": open_time, "close": close_time, "closed": closed} for d in range(7)]


def _fresh_phone(tag=""):
    return "0399" + tag + str(int(time.time() * 1000))[-7:] + uuid.uuid4().hex[:2]


def _reset(phone):
    return requests.post(f"{API}/chat/{SLUG}/reset", params={"phone": phone}, timeout=60)


def _send(phone, text, cmid=None):
    body = {"phone": phone, "text": text, "client_message_id": cmid or str(uuid.uuid4())}
    return requests.post(f"{API}/chat/{SLUG}/message", json=body, timeout=AI_TIMEOUT)


# ------------------------- fixtures -------------------------
@pytest.fixture(scope="session")
def owner_headers():
    r = requests.post(f"{API}/auth/login", json=OWNER, timeout=60)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _put_settings(headers, **body):
    r = requests.put(f"{API}/restaurant/settings", json=body, headers=headers, timeout=60)
    assert r.status_code == 200, f"settings update failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module", autouse=True)
def _restore_hours_at_end(owner_headers):
    yield
    # Always restore the demo state
    _put_settings(owner_headers, opening_hours=_week_open(), allow_orders_when_closed=False)


# ============================================================
# UNIT TESTS  is_open()
# ============================================================
class TestIsOpenUnit:
    """Direct calls to services.orders.is_open() with injected UTC datetimes."""

    def _utc(self, weekday, hh, mm):
        # Build a UTC datetime that maps to a specific PKT weekday+hour+min (PKT = UTC+5).
        # Pick a base date whose weekday() aligns to the requested weekday when +5h added.
        # 2024-01-01 = Monday. Add days so PKT date's weekday matches.
        base_pkt_h = hh
        base_pkt_m = mm
        # UTC = PKT - 5h
        utc_h = base_pkt_h - 5
        day_offset = weekday  # 2024-01-01 is Mon (weekday 0)
        # Handle negative UTC hour by shifting a day back
        if utc_h < 0:
            utc_h += 24
            day_offset -= 1
        year, month = 2024, 1
        day = 1 + day_offset
        # Clamp within January
        while day < 1:
            day += 7
        return datetime(year, month, day, utc_h, base_pkt_m, tzinfo=timezone.utc)

    def test_open_11_23_at_13_pkt(self):
        s = {"opening_hours": _week_open("11:00", "23:59")}
        open_now, _ = is_open(s, now=self._utc(weekday=0, hh=13, mm=0))
        assert open_now is True

    def test_closed_11_23_at_09_pkt(self):
        s = {"opening_hours": _week_open("11:00", "23:59")}
        open_now, opens_at = is_open(s, now=self._utc(weekday=0, hh=9, mm=0))
        assert open_now is False
        assert opens_at == "11:00"

    def test_closed_11_23_at_02_pkt(self):
        s = {"opening_hours": _week_open("11:00", "23:59")}
        open_now, opens_at = is_open(s, now=self._utc(weekday=0, hh=2, mm=0))
        assert open_now is False
        assert opens_at == "11:00"

    def test_overnight_18_02_open_at_20_pkt(self):
        s = {"opening_hours": _week_open("18:00", "02:00")}
        open_now, _ = is_open(s, now=self._utc(weekday=1, hh=20, mm=0))
        assert open_now is True

    def test_overnight_18_02_open_at_01_pkt(self):
        s = {"opening_hours": _week_open("18:00", "02:00")}
        # 01:00 PKT on Tue - the Mon 18-02 window is still active
        open_now, _ = is_open(s, now=self._utc(weekday=1, hh=1, mm=0))
        assert open_now is True

    def test_overnight_18_02_closed_at_10_pkt(self):
        s = {"opening_hours": _week_open("18:00", "02:00")}
        open_now, opens_at = is_open(s, now=self._utc(weekday=1, hh=10, mm=0))
        assert open_now is False
        assert opens_at == "18:00"

    def test_all_days_closed(self):
        s = {"opening_hours": _week_open(closed=True)}
        open_now, opens_at = is_open(s, now=self._utc(0, 13, 0))
        assert open_now is False
        assert opens_at == ""

    def test_empty_opening_hours(self):
        open_now, opens_at = is_open({"opening_hours": []}, now=self._utc(0, 13, 0))
        assert open_now is True
        assert opens_at == ""

    def test_mixed_week_next_opening(self):
        # Only Sunday (day=6) closed; today is Sunday.
        hours = _week_open("11:00", "23:59")
        hours[6]["closed"] = True
        # Use a Sunday morning PKT
        s = {"opening_hours": hours}
        open_now, opens_at = is_open(s, now=self._utc(weekday=6, hh=9, mm=0))
        assert open_now is False
        # Next opening = Monday 11:00 (day 0)
        assert opens_at == "11:00"


# ============================================================
# LANGUAGE DETECTION (regression + new ambiguous handling)
# ============================================================
class TestLanguageDetection:
    def test_menu_dikhayen_is_roman_urdu(self):
        assert detect_language("menu dikhayen") == "roman_ur"

    def test_zinger_urdu_phrase(self):
        assert detect_language("1 zinger burger aur fries") == "roman_ur"

    def test_yes_place_my_order_stays_english(self):
        # 'order' alone should NOT flip to roman_ur (ambiguous hint).
        assert detect_language("Yes, place my order") == "en"

    def test_do_you_deliver_stays_english(self):
        assert detect_language("Do you deliver to F-7?") == "en"

    def test_urdu_script(self):
        assert detect_language("مینو دکھائیں") == "ur"

    def test_plain_english(self):
        assert detect_language("Hi") == "en"


# ============================================================
# PUBLIC /api/chat/{slug} exposes open_now / opens_at
# ============================================================
class TestPublicChatMeta:
    def test_public_endpoint_has_open_now(self, owner_headers):
        # Ensure demo state - hours open
        _put_settings(owner_headers, opening_hours=_week_open(), allow_orders_when_closed=False)
        r = requests.get(f"{API}/chat/{SLUG}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "open_now" in d
        assert "opens_at" in d
        assert d["open_now"] is True

    def test_public_endpoint_reflects_closed(self, owner_headers):
        _put_settings(owner_headers, opening_hours=_week_open(closed=True), allow_orders_when_closed=False)
        try:
            r = requests.get(f"{API}/chat/{SLUG}", timeout=30)
            assert r.status_code == 200
            d = r.json()
            assert d["open_now"] is False
        finally:
            _put_settings(owner_headers, opening_hours=_week_open(), allow_orders_when_closed=False)


# ============================================================
# CLOSED-HOURS CHAT GATE
# ============================================================
class TestClosedHoursGate:
    def test_closed_gate_blocks_and_returns_metadata(self, owner_headers):
        # Close all 7 days
        _put_settings(owner_headers, opening_hours=_week_open(closed=True), allow_orders_when_closed=False)
        try:
            orders_before = len(requests.get(f"{API}/orders", headers=owner_headers, timeout=60).json())
            phone = _fresh_phone("cl")
            _reset(phone)
            r = _send(phone, "Hi")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data.get("closed") is True, f"expected closed=true, got {data}"
            assert "opens_at" in data
            assert isinstance(data.get("replies"), list) and len(data["replies"]) == 1
            reply = data["replies"][0].lower()
            assert "closed" in reply or "close" in reply, f"reply missing closed text: {reply}"

            # Follow-up attempting to order must ALSO be refused
            r2 = _send(phone, "1 zinger burger")
            assert r2.status_code == 200
            data2 = r2.json()
            assert data2.get("closed") is True
            assert len(data2["replies"]) == 1

            # No new order was created
            orders_after = requests.get(f"{API}/orders", headers=owner_headers, timeout=60).json()
            assert len([o for o in orders_after if o.get("customer_phone") == phone]) == 0
            assert len(orders_after) == orders_before
        finally:
            _put_settings(owner_headers, opening_hours=_week_open(), allow_orders_when_closed=False)

    def test_closed_message_roman_urdu(self, owner_headers):
        _put_settings(owner_headers, opening_hours=_week_open(closed=True), allow_orders_when_closed=False)
        try:
            phone = _fresh_phone("cru")
            _reset(phone)
            r = _send(phone, "menu dikhayen")
            assert r.status_code == 200
            data = r.json()
            assert data.get("closed") is True
            reply = data["replies"][0].lower()
            # Roman-Urdu markers
            assert "closed hai" in reply or "opening time" in reply, f"not roman-urdu closed msg: {reply}"
        finally:
            _put_settings(owner_headers, opening_hours=_week_open(), allow_orders_when_closed=False)

    def test_closed_message_urdu_script(self, owner_headers):
        _put_settings(owner_headers, opening_hours=_week_open(closed=True), allow_orders_when_closed=False)
        try:
            phone = _fresh_phone("cur")
            _reset(phone)
            r = _send(phone, "مینو دکھائیں")
            assert r.status_code == 200
            data = r.json()
            assert data.get("closed") is True
            import re as _re
            assert _re.search(r"[\u0600-\u06FF]", data["replies"][0]), "Urdu-script reply expected"
        finally:
            _put_settings(owner_headers, opening_hours=_week_open(), allow_orders_when_closed=False)

    def test_closed_message_english(self, owner_headers):
        _put_settings(owner_headers, opening_hours=_week_open(closed=True), allow_orders_when_closed=False)
        try:
            phone = _fresh_phone("cen")
            _reset(phone)
            r = _send(phone, "Hi")
            assert r.status_code == 200
            reply = r.json()["replies"][0]
            assert "closed" in reply.lower() and "open" in reply.lower()
        finally:
            _put_settings(owner_headers, opening_hours=_week_open(), allow_orders_when_closed=False)


# ============================================================
# PRE-ORDER OVERRIDE
# ============================================================
class TestPreorderOverride:
    def test_preorder_toggle_lets_bot_work_when_closed(self, owner_headers):
        # Close all days + allow pre-orders
        _put_settings(owner_headers, opening_hours=_week_open(closed=True), allow_orders_when_closed=True)
        try:
            phone = _fresh_phone("pre")
            _reset(phone)
            r = _send(phone, "Hi")
            assert r.status_code == 200
            data = r.json()
            # Bot must NOT return closed=true; it should engage normally.
            assert data.get("closed") is not True, f"AI blocked despite preorder toggle: {data}"
            assert isinstance(data.get("replies"), list) and len(data["replies"]) >= 1
        finally:
            _put_settings(owner_headers, opening_hours=_week_open(closed=True), allow_orders_when_closed=False)

    def test_toggle_off_reblocks(self, owner_headers):
        # Already closed + allow_orders_when_closed=False from teardown above
        _put_settings(owner_headers, opening_hours=_week_open(closed=True), allow_orders_when_closed=False)
        try:
            phone = _fresh_phone("preoff")
            _reset(phone)
            r = _send(phone, "Hi")
            assert r.status_code == 200
            assert r.json().get("closed") is True
        finally:
            _put_settings(owner_headers, opening_hours=_week_open(), allow_orders_when_closed=False)


# ============================================================
# RESTORED HOURS -> BOT WORKS AGAIN
# ============================================================
class TestBotResumesWhenOpen:
    def test_hi_returns_ai_greeting_when_open(self, owner_headers):
        _put_settings(owner_headers, opening_hours=_week_open(), allow_orders_when_closed=False)
        phone = _fresh_phone("open")
        _reset(phone)
        r = _send(phone, "Hi")
        assert r.status_code == 200
        data = r.json()
        assert data.get("closed") is not True
        assert isinstance(data.get("replies"), list) and len(data["replies"]) >= 1
