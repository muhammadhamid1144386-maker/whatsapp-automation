# AI Restaurant Assistant

A multi-tenant, AI-powered WhatsApp ordering platform for restaurants in Pakistan. A customer chats on
WhatsApp, the AI takes the order, the backend prices it, and the restaurant's dashboard lights up in
real time. Every status change flows straight back to the customer on WhatsApp.

---

## 1. Project overview

| Capability | Status |
| --- | --- |
| AI ordering agent (English / Urdu / Roman Urdu) | Working |
| WhatsApp channel with provider abstraction + built-in simulator | Working |
| Server-side cart, backend-only price calculation, price snapshots | Working |
| Real-time dashboard over Server-Sent Events | Working |
| Order lifecycle + status history + WhatsApp notifications | Working |
| Menu / categories / add-ons management | Working |
| Customer database + history | Working |
| Conversations with AI ⇄ human handoff | Working |
| Analytics | Working |
| Google Sheets sync engine (jobs, retries, states) | Working — **not connected** until you add credentials |
| Multi-tenant isolation, JWT auth, rate limiting, audit logs | Working |

### Deviations from the original brief (and why)

The brief asked for Next.js + PostgreSQL + Prisma + Baileys. This deployment runs on the platform's
managed stack, so two substitutions were agreed with the product owner before building:

1. **MongoDB instead of PostgreSQL/Prisma.** PostgreSQL is not available in this environment. The
   schema, collections, tenant scoping and "database is the source of truth" rules are identical —
   only the driver differs. Google Sheets is still strictly a mirror, never the transactional store.
2. **WhatsApp Simulator instead of a live Baileys QR pairing.** Baileys / whatsapp-web.js needs a
   long-lived Node process plus a real phone scanning a QR, which is not reliable in a sandboxed
   container. Instead the `WhatsAppProvider` abstraction ships with a fully working `SimulatorProvider`
   so the entire 43-step flow genuinely runs end to end, and a `BaileysProvider` slot that only needs
   a bridge URL to take over.

---

## 2. Architecture

```
WhatsApp customer (or Simulator UI)
        │
        ▼
WhatsAppProvider  ── SimulatorProvider | BaileysProvider | OfficialWhatsAppProvider
        │
        ▼
Message processor      services/processor.py     (idempotency, persistence, state)
        │
        ▼
AI agent               services/agent.py         (system prompt + 16 validated tools)
        │              services/ai.py            (AIProvider → Gemini | Ollama)
        ▼
Backend tools ── menu · cart · customer · pricing        (LLM never touches the DB)
        │
        ▼
Order service          services/orders.py        (validate → snapshot → total → create)
        │
        ├──▶ MongoDB (source of truth)
        ├──▶ EventBroker → SSE → restaurant dashboard      (NEW_ORDER instantly)
        ├──▶ NotificationService → WhatsApp → customer
        └──▶ google_sync_jobs queue → background worker → Google Sheets
```

Key guarantees:

- **The AI never computes money.** Every total comes from `services/orders.calculate_totals`.
- **The AI never invents data.** It can only call the tools in `services/agent.TOOLS`.
- **Sheets can never break an order.** Sync is a queued job with `pending → synced → failed` states,
  automatic retries (max 5 attempts) and a 30s background worker.
- **Tenant isolation is enforced server-side.** Every protected route resolves `restaurant_id` from the
  JWT via the `tenant` dependency; no query ever trusts a client-supplied restaurant id.

---

## 3. Tech stack

- **Frontend** — React 19, React Router 7, Tailwind CSS, shadcn/ui, Recharts, Sonner, lucide-react
- **Backend** — FastAPI (Python), Motor (async MongoDB), PyJWT, bcrypt
- **Database** — MongoDB
- **Real-time** — Server-Sent Events (`/api/events/stream`, `/api/chat/{slug}/stream`)
- **AI** — Gemini 3 Flash via the Emergent universal LLM key (`AI_PROVIDER=gemini`); Ollama slot scaffolded
- **WhatsApp** — provider abstraction; Simulator (default) or Baileys bridge
- **Sheets** — `gspread` + `google-auth` service account

### Layout

```
backend/
  server.py                 app assembly, startup seed, background worker
  core/db.py                Mongo client, PyObjectId, BaseDocument, indexes, sequences
  core/security.py          bcrypt, JWT, get_current_user, tenant guard, rate limit, audit
  models.py                 all 17 document models + enums
  seed.py                   idempotent Pizza Palace demo seed
  services/
    realtime.py             EventBroker + SSE formatting
    whatsapp.py             WhatsAppProvider, SimulatorProvider, BaileysProvider, factory
    ai.py                   AIProvider, GeminiProvider, OllamaProvider, language detection
    agent.py                system prompt, 16 backend tools, dispatcher, fallback
    processor.py            inbound pipeline, idempotency, staff replies
    cart.py                 server-side cart
    orders.py               pricing, creation, status machine
    notifications.py        NotificationService + localised message templates
    sheets.py               job queue, retry, tab schemas, background worker
  routers/                  auth, restaurant, menu, orders, people, channels, events, chat
frontend/src/
  pages/                    Login, Dashboard, Orders, OrderDetail, Customers, MenuPage,
                            Conversations, WhatsAppPage, GoogleSheets, Analytics, Settings, ChatDemo
  components/               DashboardLayout, OrderCard, StatusBadge, WhatsAppSimulator, ui/
  hooks/useRealtime.js      SSE hooks + new-order chime
  lib/api.js                axios client, token store, formatters
```

---

## 4. Installation

Both services are supervisor-managed and already running.

```bash
# backend deps
cd /app/backend && pip install -r requirements.txt

# frontend deps (yarn only — never npm)
cd /app/frontend && yarn install

sudo supervisorctl restart backend frontend
```

---

## 5. Environment variables

`backend/.env`

| Variable | Purpose |
| --- | --- |
| `MONGO_URL` | Mongo connection string (managed) |
| `DB_NAME` | Database name (managed) |
| `CORS_ORIGINS` | Allowed origins |
| `JWT_SECRET` | Session signing secret |
| `EMERGENT_LLM_KEY` | Universal key for Gemini |
| `AI_PROVIDER` | `gemini` (default) or `ollama` |
| `AI_MODEL` | `gemini-3-flash-preview` |
| `WHATSAPP_PROVIDER` | `simulator` (default) or `baileys` |
| `BAILEYS_BRIDGE_URL` | Node sidecar URL, required only for `baileys` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account JSON (single line). Empty = Sheets not connected |
| `GOOGLE_SHEET_ID` | Default spreadsheet id |
| `DEMO_MODE` | `true` seeds Pizza Palace on boot |
| `DEMO_OWNER_EMAIL` / `DEMO_OWNER_PASSWORD` | Seeded owner login |

`frontend/.env` — `REACT_APP_BACKEND_URL` only. **No secret ever reaches the frontend.**

---

## 6. Database setup

Nothing manual. On startup `core.db.ensure_indexes()` creates every index (including the unique
constraints that make orders and inbound messages idempotent) and `seed.seed_demo()` seeds the demo
restaurant if it is missing.

Collections: `restaurants`, `users`, `restaurant_settings`, `customers`, `conversations`, `messages`,
`menu_categories`, `menu_items`, `menu_addons`, `carts`, `orders`, `order_items`,
`order_status_history`, `whatsapp_sessions`, `whatsapp_logs`, `google_sheet_connections`,
`google_sync_jobs`, `processed_messages`, `counters`, `audit_logs`, `login_attempts`.

---

## 7. Gemini setup

Already wired. `AI_PROVIDER=gemini` and `AI_MODEL=gemini-3-flash-preview` run through the Emergent
universal key, so no Google AI Studio key is required. To use your own provider, swap
`EMERGENT_LLM_KEY` and adjust `services/ai.GeminiProvider`.

If the model call fails, the agent does **not** crash the order system: it replies with a graceful
fallback and flips the conversation to human handoff, which raises a dashboard alert.

---

## 8. WhatsApp setup

**Simulator (default)** — go to **WhatsApp → Connect**. Status becomes `connected`. The phone-shaped
chat on the right (also at `/chat`, no login needed) is a real customer session: messages go through
the same processor, agent, cart and order code as production.

**Baileys (optional, unofficial)** — run a Node sidecar with `@whiskeysockets/baileys` exposing
`/connect`, `/status`, `/qr`, `/send`, `/disconnect`, then set:

```
WHATSAPP_PROVIDER=baileys
BAILEYS_BRIDGE_URL=http://localhost:3100
```

Only `services/whatsapp.BaileysProvider` needs filling in — AI, orders, customers, dashboard,
analytics, notifications and Sheets stay untouched.

---

## 9. Google Sheets setup

1. Google Cloud Console → create a **service account** → create a JSON key.
2. Enable the **Google Sheets API** and **Google Drive API**.
3. Create a spreadsheet and **share it with the service account email** as Editor.
4. Put the JSON (single line) into `GOOGLE_SERVICE_ACCOUNT_JSON` in `backend/.env`, then
   `sudo supervisorctl restart backend`.
5. Dashboard → **Google Sheets** → paste the spreadsheet id → **Connect** → **Sync now**.

Tabs are created automatically with headers: `Orders`, `Customers`, `Order Items`, `Messages`,
`Daily Summary`.

Until step 4 the page correctly reports **Not connected** and jobs stay `pending` — orders are
completely unaffected. This is the shipped default.

---

## 10. Running locally

```bash
sudo supervisorctl status                 # both services
tail -n 100 /var/log/supervisor/backend.*.log
```

Frontend: `/login` · Customer demo: `/chat` · API root: `/api/`

---

## 11. Demo restaurant

**Pizza Palace**, Islamabad. Delivery fee PKR 150, minimum order PKR 500, prep 20–30 min,
delivery 15–20 min (so delivery ETA 35–50, pickup 20–30). Open 11:00–23:59 daily.

Categories: Burgers, Pizza, Rice, Fries, Drinks, Desserts. Sample prices: Zinger Burger 650,
Fries 250, Coke 120, Large Pizza 1499, Brownie 350, Chicken Biryani 480. Add-ons configured for
upselling: Fries, Coke, Extra Cheese, Garlic Mayo Dip.

Owner login: `owner@pizzapalace.pk` / `Pizza123!`

---

## 12. Testing the complete order flow

Open two tabs: **Orders** (dashboard) and **/chat** (customer).

1. WhatsApp page → **Connect** → status `connected`.
2. In the chat send `Hi` → the AI greets you.
3. `menu dikhayen` → the AI lists real categories and prices.
4. `1 zinger burger aur fries` → both items land in the server-side cart.
5. The AI suggests one add-on (e.g. Coke). Say `haan` → it is added. Decline once and it never asks again.
6. `delivery` → the AI asks for your name and address.
7. Give a name and address → the AI shows the summary: items, subtotal, delivery fee, total, ETA 35–50 min.
8. `confirm` → order created, `ORD-1001` returned, confirmation sent to the customer.
9. The **Orders** tab shows the new card **without a refresh**, with a toast and a chime.
10. Click **Confirm → Preparing → Ready → Out for delivery → Delivered**. Each click writes status
    history, updates the board live, and pushes a WhatsApp message that appears in the chat instantly.
11. Check **Customers** (totals updated), **Conversations** (full transcript), **Order detail**
    (timeline + sync status), **Analytics** (numbers moved), **Google Sheets** (jobs queued).

### API smoke test

```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
TOKEN=$(curl -s -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"owner@pizzapalace.pk","password":"Pizza123!"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s "$API/api/analytics/summary" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$API/api/chat/pizza-palace/message" -H 'Content-Type: application/json' \
  -d '{"phone":"03001234567","text":"Hi","client_message_id":"t1"}'
```

---

## 13. Troubleshooting

| Symptom | Fix |
| --- | --- |
| Dashboard does not update live | SSE needs the token in the URL; log out and back in. Check `/api/events/stream?token=…`. |
| AI replies with the fallback message | Gemini call failed. Check `tail -n 100 /var/log/supervisor/backend.err.log` and `EMERGENT_LLM_KEY` balance. The conversation is flipped to human handoff — toggle AI back on in **Conversations**. |
| "Restaurant is currently closed" | Settings → Hours, or enable pre-orders in Settings → Operations. |
| "Minimum order is PKR 500" | Add more items, or lower the minimum in Settings → Operations. |
| Sheets jobs stuck on `pending` | Expected until `GOOGLE_SERVICE_ACCOUNT_JSON` is set. See section 9. |
| Duplicate WhatsApp messages | Handled — `processed_messages.external_id` is unique, and order creation is idempotent per cart. |
| Login says too many attempts | 5 failures locks that IP+email for 15 minutes. |

---

## 14. Production considerations

- Move `EventBroker` to Redis pub/sub before running more than one backend replica.
- Move the Sheets worker into a dedicated queue (Celery / Arq) with exponential backoff.
- Rotate `JWT_SECRET`, shorten the access token TTL, and put a real WAF/rate limiter at the edge.
- Store WhatsApp session credentials encrypted at rest, per tenant.
- Add per-tenant AI spend caps and structured request logging.
- `audit_logs` already records logins, status changes and menu/settings edits — ship them to your SIEM.

## 15. WhatsApp safety

This project deliberately implements **no** bulk messaging, broadcasts, unsolicited outreach, scraping
or contact harvesting. Outbound messages only ever reply to a customer who messaged first, or notify
that same customer about their own order.

The optional Baileys / whatsapp-web.js path is an **unofficial WhatsApp Web library**, not the official
WhatsApp Business API. Use it only for controlled development and demos, with numbers and conversations
you are authorised to use. Production deployments should migrate to the official WhatsApp Business API.

## 16. WhatsApp provider migration

```
WhatsAppProvider (abstract: connect, disconnect, get_status, get_qr_code,
                  send_message, send_image, send_document)
   ├── SimulatorProvider           ← default, ships working
   ├── BaileysProvider             ← unofficial bridge, opt-in
   └── OfficialWhatsAppProvider    ← add for production
```

To migrate: add the new class in `services/whatsapp.py`, register it in `get_whatsapp_provider()`,
set `WHATSAPP_PROVIDER`. Nothing else changes — the AI, orders, customers, database, dashboard,
analytics, Sheets sync and notification service are all provider-agnostic.
