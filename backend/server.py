import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from core.db import client, ensure_indexes  # noqa: E402
from routers import auth, channels, chat, events, menu, orders, people, restaurant  # noqa: E402
from seed import seed_demo  # noqa: E402
from services.sheets import sync_worker  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ai-restaurant")

app = FastAPI(title="AI Restaurant Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, restaurant, menu, orders, people, channels, events, chat):
    app.include_router(module.router)

_background: list[asyncio.Task] = []


@app.get("/api/")
async def root():
    return {
        "service": "AI Restaurant Assistant",
        "status": "ok",
        "demo_mode": os.environ.get("DEMO_MODE", "true") == "true",
        "ai_provider": os.environ.get("AI_PROVIDER", "gemini"),
        "whatsapp_provider": os.environ.get("WHATSAPP_PROVIDER", "simulator"),
    }


@app.get("/api/health")
async def health():
    from core.db import db

    await db.command("ping")
    return {"ok": True}


@app.on_event("startup")
async def startup() -> None:
    await ensure_indexes()
    info = await seed_demo()
    logger.info("startup complete %s", info)
    _background.append(asyncio.create_task(sync_worker()))


@app.on_event("shutdown")
async def shutdown() -> None:
    for task in _background:
        task.cancel()
    client.close()
