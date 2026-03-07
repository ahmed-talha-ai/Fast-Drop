# core/config.py — Application Settings
# ═══════════════════════════════════════
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central configuration loaded from .env"""

    # ── LLM API Keys ──────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    HUGGINGFACE_API_TOKEN: str = os.getenv("HUGGINGFACE_API_TOKEN", "")

    # ── Telegram ──────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # ── Maps & Geocoding ──────────────────────────────
    GOOGLE_MAPS_KEY: str = os.getenv("GOOGLE_MAPS_KEY", "")
    OPENCAGE_API_KEY: str = os.getenv("OPENCAGE_API_KEY", "")

    # ── Database & Cache ──────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./fastdrop.db"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # ── Application ───────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "ar")
    SUPPORTED_LANGUAGES: list = os.getenv(
        "SUPPORTED_LANGUAGES", "ar,en"
    ).split(",")
    DOMAIN: str = os.getenv("DOMAIN", "localhost")

    # ── JWT Auth ──────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Rate Limits (daily) ───────────────────────────
    GROQ_DAILY_LIMIT: int = 14_400
    GEMINI_DAILY_LIMIT: int = 1_000
    OPENROUTER_DAILY_LIMIT: int = 200

    # ── LLM Model IDs ────────────────────────────────
    # Arabic-capable models (priority order)
    GROQ_ARABIC_MODELS: list = [
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "llama-3.3-70b-versatile",
        "gemma2-9b-it",
    ]
    GROQ_FAST_MODELS: list = [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "gemma2-9b-it",
    ]
    GEMINI_MODELS: list = [
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ]
    OPENROUTER_ARABIC_MODELS: list = [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "google/gemma-3-27b-it:free",
        "deepseek/deepseek-r1:free",
        "qwen/qwen3-32b:free",
    ]

    # ── Embedding Model ──────────────────────────────
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"


settings = Settings()
