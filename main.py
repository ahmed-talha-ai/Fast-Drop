# main.py
# ═══════════════════════════════════════════════════════════════════
# Fast Drop — AI-Powered Delivery Management System
# البرنامج الرئيسي — فاست دروب
# ═══════════════════════════════════════════════════════════════════
# Run: python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
# Docs: http://localhost:8000/docs (Swagger)
#       http://localhost:8000/redoc (ReDoc)
# ═══════════════════════════════════════════════════════════════════
import os
import logging
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, close_db

# ── Logging Setup ─────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fastdrop")


# ═══════════════════════════════════════════════
# Application Lifespan
# ═══════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("🚚 Fast Drop starting up...")

    # ── 1. Initialize Database ────────────────
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.warning(f"⚠️ Database init skipped: {e}")

    # ── 2. Build RAG Index ────────────────────
    try:
        from rag.build_index import load_index
        vector_index, bm25_retriever = load_index()
        if vector_index and bm25_retriever:
            # Inject into chat API
            from api.chat import set_rag_components
            set_rag_components(vector_index, bm25_retriever)
            logger.info("✅ LlamaIndex RAG components loaded")
        else:
            logger.warning("⚠️ RAG index unavailable — chatbot will work without knowledge base")
    except Exception as e:
        logger.warning(f"⚠️ LlamaIndex RAG init skipped: {e}")
        vector_index, bm25_retriever = None, None

    # ── 3. Start Telegram Bot ─────────────────
    telegram_task = None
    try:
        from tg_bot.bot import create_bot_app
        bot_app = create_bot_app()
        # Inject RAG components for chat handlers
        bot_app.bot_data["vector_index"] = locals().get("vector_index")
        bot_app.bot_data["bm25_retriever"] = locals().get("bm25_retriever")

        # Start polling in background
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        logger.info("✅ Telegram bot started (polling mode)")
    except Exception as e:
        logger.warning(f"⚠️ Telegram bot skipped: {e}")

    logger.info("═" * 50)
    logger.info("🟢 Fast Drop is ready! فاست دروب جاهز!")
    logger.info("═" * 50)

    yield  # ── Application runs here ──

    # ── Shutdown ──────────────────────────────
    logger.info("🔴 Fast Drop shutting down...")
    try:
        if telegram_task:
            telegram_task.cancel()
        if 'bot_app' in dir():
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
    except Exception:
        pass

    await close_db()
    logger.info("👋 Fast Drop stopped. مع السلامة!")


# ═══════════════════════════════════════════════
# FastAPI Application
# ═══════════════════════════════════════════════
app = FastAPI(
    title="Fast Drop API — فاست دروب",
    description=(
        "AI-Powered Delivery Management System for Egypt 🇪🇬\n"
        "Bilingual: Egyptian Arabic + English\n\n"
        "خدمة توصيل ذكية مدعومة بالذكاء الاصطناعي"
    ),
    version="4.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════
# Mount API Routers
# ═══════════════════════════════════════════════
from api.orders import router as orders_router
from api.drivers import router as drivers_router
from api.analytics import router as analytics_router
from api.chat import router as chat_router
from api.ai_endpoints import router as ai_router
from auth.jwt import router as auth_router

app.include_router(auth_router)
app.include_router(orders_router)
app.include_router(drivers_router)
app.include_router(analytics_router)
app.include_router(chat_router)
app.include_router(ai_router)


# ═══════════════════════════════════════════════
# Root Endpoints
# ═══════════════════════════════════════════════
@app.get("/")
async def root():
    """
    Health check + system info.
    فحص الحالة + معلومات النظام
    """
    return {
        "service": "Fast Drop AI — فاست دروب",
        "version": "4.0.0",
        "status": "running ✅",
        "language": os.getenv("DEFAULT_LANGUAGE", "ar"),
        "endpoints": {
            "docs": "/docs",
            "orders": "/api/orders",
            "drivers": "/api/drivers",
            "analytics": "/api/analytics",
            "chat": "/api/chat",
            "auth": "/api/auth",
        },
        "message_ar": "أهلاً بيك في فاست دروب! 🚚",
        "message_en": "Welcome to Fast Drop! 🚚",
    }


@app.get("/health")
async def health_check():
    """Detailed health check for monitoring."""
    checks = {
        "api": "ok",
        "database": "unknown",
        "redis": "unknown",
        "rag": "unknown",
    }

    # Check DB
    try:
        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # Check Redis
    try:
        import redis
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    # Check RAG
    try:
        from api.chat import _rag_components
        if _rag_components.get("vector_index"):
            checks["rag"] = "ok (LlamaIndex loaded)"
        else:
            checks["rag"] = "not loaded"
    except Exception:
        checks["rag"] = "error"

    all_ok = all(v == "ok" or v.startswith("ok") for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
    }


@app.get("/api/zones")
async def list_zones():
    """List all Cairo delivery zones."""
    from core.zone_manager import get_all_zones
    return {"zones": get_all_zones()}
