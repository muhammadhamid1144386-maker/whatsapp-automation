# PRD — AI Restaurant Assistant

Multi-tenant, AI-powered WhatsApp ordering SaaS for restaurants in Pakistan.

## Original problem statement (condensed)

Build a genuinely working MVP (not a UI prototype) of a multi-tenant AI restaurant ordering platform:
WhatsApp AI chatbot (English / Urdu / Roman Urdu), AI-powered ordering, restaurant dashboard, real-time
order updates with no browser refresh, customer management, conversation history, menu management,
automatic bill calculation, AI upselling, order status management, automatic WhatsApp notifications,
PostgreSQL database, Google Sheets synchronisation, authentication, restaurant profiles, demo mode.
Currency PKR. The AI must never invent menu items, prices, delivery fees, opening hours, delivery times
or totals — all business-critical values come from backend tools. Google Sheets must never be the
transactional store and must never block order creation. Prevent duplicate orders from duplicate
WhatsApp messages. Seed a demo restaurant "Pizza Palace". The full 43-step demo flow must work.

## Agreed deviations (confirmed with the user before building)

| Brief | Shipped | Why |
| --- | --- | --- |
| PostgreSQL + Prisma | MongoDB (same collections, same tenant scoping, same source-of-truth rules) | PostgreSQL is not available in this environment |
| Baileys / whatsapp-web.js live QR | `WhatsAppProvider` abstraction + working built-in **Simulator**; `BaileysProvider` stub wired for later | Baileys needs a long-lived Node process + a real phone scanning a QR, unreliable in a sandbox |
| Next.js | React (CRA) + FastAPI | Platform stack |
| Gemini API key | Gemini 3 Flash (`gemini-3-flash-preview`) via the Emergent universal key | No key needed from the user |
| Google Sheets connected | Full sync engine built, intentionally left **unconnected** | Requires the user's service-account JSON |

## Architecture

```
WhatsApp customer / Simulator UI
  → WhatsAppProvider (Simulator | Baileys | OfficialWhatsApp)
  → processor.handle_incoming   (idempotency → persist → conversation state)
  → agent.respond               (system prompt + 16 validated backend tools)
  → ai.GeminiProvider           (tool-calling loop)
  → backend tools               (menu · cart · customer · pricing)
  → orders.create_order         (re-validate → price snapshot → total)
       ├→ MongoDB (source of truth)
       ├→ EventBroker → SSE → dashboard (NEW_ORDER, no refresh)
       ├→ NotificationService → WhatsApp → customer
       └→ google_sync_jobs queue → background worker → Google Sheets
```

Backend: `core/db.py`, `core/security.py`, `models.py`, `seed.py`,
`services/{realtime,whatsapp,ai,agent,processor,cart,orders,notifications,sheets}.py`,
`routers/{auth,restaurant,menu,orders,people,channels,events,chat}.py`.
Frontend: 12 pages, `DashboardLayout`, `OrderCard`, `StatusBadge`, `WhatsAppSimulator`, `useRealtime`.

## User personas

- **Restaurant owner (primary)** — non-technical, on a phone between kitchen and counter. Needs new
  orders to be impossible to miss and status changes to be one tap.
- **Kitchen / counter staff** — works the live board, takes over a chat when a customer gets difficult.
- **Customer** — orders on WhatsApp in Roman Urdu, expects short replies and an accurate bill.
- **Platform operator** — onboards new restaurants; relies on strict tenant isolation.

## Core requirements (static)

1. MongoDB is the single source of truth; Google Sheets is a mirror only.
2. The LLM never touches the database and never computes money. `orders.calculate_totals` is the only
   pricing authority.
3. Estimated times derive from restaurant settings (prep + delivery), never from the AI.
4. Strict backend-enforced tenant isolation via the `tenant()` dependency.
5. Price snapshots — changing a menu price must never alter a historical order.
6. Idempotent inbound messages and idempotent order creation.
7. Sheets sync is async with `pending → synced → failed` and automatic retries; it can never fail an order.
8. One upsell suggestion maximum; never repeated after a decline.
9. WhatsApp transport is swappable behind `WhatsAppProvider`. No bulk/unsolicited messaging, ever.

## Implemented — 2026-06 (initial build)

- **Auth & tenancy**: bcrypt + JWT (Bearer / httpOnly cookie / `?token=` for SSE), register, refresh,
  logout, brute-force lockout (5 tries / 15 min), in-memory rate limiting, audit logs, `tenant()` guard.
- **Data model**: 21 collections with unique indexes on `orders.order_number`,
  `orders.idempotency_key`, `processed_messages.external_id`, `carts.conversation_id`,
  `whatsapp_sessions.restaurant_id`; per-restaurant `ORD-1000+` sequence.
- **AI agent**: `AIProvider` → Gemini (default) / Ollama slot. 16 backend tools. Rule-based language
  detection (Urdu script / Roman Urdu / English). Graceful fallback + `AI_ERROR` alert on provider failure.
- **Ordering**: server-side cart, live menu re-validation, price snapshots, min-order and
  open/closed guards, delivery vs pickup collection rules, ETA from settings.
- **Order lifecycle**: 8 statuses with an enforced transition table, `order_status_history`,
  localised WhatsApp notification per status, reject-with-reason flow.
- **Real-time**: SSE `EventBroker`; dashboard stream + per-customer stream; toast + Web Audio chime.
- **Dashboard**: 12 pages — Dashboard, Orders (live kanban), Order detail (timeline + sync),
  Customers, Menu (category/item/add-on CRUD + availability), Conversations (AI ⇄ human handoff,
  staff reply), WhatsApp (connect / QR / disconnect / logs / embedded simulator), Google Sheets,
  Analytics (Recharts), Settings (profile / operations / hours / AI), public `/chat` demo.
- **Sheets**: job queue, 5-attempt retry, 30s worker, 5 tab schemas, Sync Now, per-order resync.
- **Demo seed**: Pizza Palace — 6 categories, 14 items, 4 upsell add-ons, settings, owner account.
- **Design**: warm terracotta / bone palette, Cabinet Grotesk + IBM Plex Sans + Noto Nastaliq Urdu,
  dark mode, mobile responsive.
- **Verified**: 30/30 backend tests + frontend smoke pass (`/app/test_reports/iteration_1.json`);
  regression suite at `/app/backend/tests/backend_test.py`.
- **Fixed during build**: WhatsApp session stuck on `connecting` (now an atomic write);
  AI infrastructure failure no longer permanently locks a chat into human handoff;
  Roman Urdu detection expanded to common verbs (`dikhayen`, `mangwana`, `batao`, …) with an
  `AMBIGUOUS_HINTS` guard so English phrases like "place my order" stay English.

## Implemented — 2026-06 (opening hours & closed-hours bot gate)

Requested by the user: editable restaurant timings in Settings, and the bot must not operate when closed.

- **Settings → Hours** is now a first-class editor: all 7 days with 24-hour open/close inputs and a
  per-day Open/Closed switch, a live **"Open right now" / "Closed right now — opens HH:MM"** banner,
  and an inline note explaining exactly what happens outside those hours. Values persist and the
  banner refreshes on save.
- **Closed-hours gate** in `processor.handle_incoming()`: outside opening hours the pipeline returns
  early with `closed: true` **before ever reaching the LLM**. The customer gets a localised
  (English / Urdu / Roman Urdu) "we're closed, we open at HH:MM" reply, nothing enters the cart, no
  order can be created, and no Gemini spend occurs. Conversation state resets to `GREETING`.
- **Pre-order override**: Settings → Operations → *Accept pre-orders while closed* re-enables the bot
  while closed, for restaurants that want to queue orders overnight.
- **`is_open()` rewritten** to handle windows that run past midnight (e.g. 18:00 → 02:00, including
  rollover from the previous day) and to report the genuine *next* opening day rather than the first
  entry in the list. `create_order()` keeps its independent server-side guard.
- **Simulator header** shows `closed · opens HH:MM`, sourced from the same `is_open()` call as the
  gate, so the UI can never disagree with the bot's behaviour.
- **Verified**: 54/54 backend tests (30 regression + 24 new closed-hours, including 9 `is_open()` unit
  cases) plus frontend Playwright checks and mobile 390×844 with zero horizontal overflow —
  `/app/test_reports/iteration_2.json`. Suite: `/app/backend/tests/test_closed_hours.py`.

## Backlog

### P0
- Connect Google Sheets for real (needs the user's service-account JSON + spreadsheet id).
- Daily Summary tab is defined but not yet populated by a scheduled roll-up job.

### P1
- Real WhatsApp: implement `BaileysProvider` against a Node sidecar, or the official Cloud API provider.
- Move `EventBroker` to Redis pub/sub so the backend can run more than one replica.
- Customer detail drawer on `/customers` (orders + transcript in one place).
- Discounts / coupons (`discount` is modelled and plumbed through but always 0).
- Multi-user restaurants: staff invites and roles beyond `owner`.

### P2
- Online payments (JazzCash, Easypaisa, Stripe), loyalty points, abandoned-cart recovery.
- Multi-branch restaurants, inventory, POS integration, rider management.
- Voice ordering, QR menu, website ordering, AI analytics.

## Next tasks

1. Populate the Daily Summary sheet from a scheduled aggregate.
2. Wire the Baileys sidecar so a real number can be paired.
3. Add the customer detail view.
4. Add coupon/discount support end to end (menu → cart → order → notification).
