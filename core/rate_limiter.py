# core/rate_limiter.py
# ═══════════════════════════════════════════════════════════
# Proactive LLM Rate Limit Monitor
# Uses Redis counters per provider per model per day.
# Pre-emptively switches to fallback BEFORE hitting 429.
# ═══════════════════════════════════════════════════════════
import os
import logging
from datetime import datetime

logger = logging.getLogger("fastdrop.ratelimit")

# ── Daily limits per model ────────────────────────────────
MODEL_DAILY_LIMITS = {
    # Groq models
    "meta-llama/llama-4-maverick-17b-128e-instruct": 500,
    "meta-llama/llama-4-scout-17b-16e-instruct": 1000,
    "llama-3.1-8b-instant": 14_400,
    "llama-3.3-70b-versatile": 1_000,
    "gemma2-9b-it": 14_400,
    # Gemini models
    "gemini-2.5-flash-lite": 1_000,
    "gemini-2.5-flash": 250,
    "gemini-2.5-pro": 100,
    # OpenRouter free models
    "google/gemini-2.0-flash-exp:free": 200,
    "meta-llama/llama-3.3-70b-instruct:free": 200,
    "mistralai/mistral-small-3.1-24b-instruct:free": 200,
    "google/gemma-3-27b-it:free": 200,
    "deepseek/deepseek-r1:free": 200,
    "qwen/qwen3-32b:free": 200,
}

# Threshold: switch when usage reaches this % of limit
SWITCH_THRESHOLD = 0.85


def _get_redis():
    """Get Redis connection (lazy)."""
    try:
        import redis
        return redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
    except Exception:
        return None


def _date_key() -> str:
    """Today's date as string for Redis key."""
    return datetime.now().strftime("%Y-%m-%d")


def increment_usage(model_id: str) -> int:
    """
    Increment request counter for a model today.
    Returns current count after increment.
    """
    r = _get_redis()
    if not r:
        return 0

    key = f"ratelimit:{model_id}:{_date_key()}"
    try:
        count = r.incr(key)
        # Set TTL to 25 hours (auto-cleanup old keys)
        if count == 1:
            r.expire(key, 90_000)
        return count
    except Exception as e:
        logger.error(f"[RateLimit] Failed to increment {model_id}: {e}")
        return 0


def get_usage(model_id: str) -> int:
    """Get current request count for a model today."""
    r = _get_redis()
    if not r:
        return 0

    key = f"ratelimit:{model_id}:{_date_key()}"
    try:
        val = r.get(key)
        return int(val) if val else 0
    except Exception:
        return 0


def is_safe_to_call(model_id: str) -> bool:
    """
    Check if a model is safe to call (below threshold).
    Returns False when usage >= 85% of daily limit → switch early.
    """
    limit = MODEL_DAILY_LIMITS.get(model_id, 999_999)
    usage = get_usage(model_id)
    threshold = int(limit * SWITCH_THRESHOLD)

    if usage >= threshold:
        logger.warning(
            f"[RateLimit] {model_id}: {usage}/{limit} "
            f"(>= {SWITCH_THRESHOLD*100}%) — pre-emptive switch"
        )
        return False
    return True


def get_best_available_model(models: list[str]) -> str | None:
    """
    From a priority-ordered list of models, return the first
    one that is still safe to call (below usage threshold).
    """
    for model in models:
        if is_safe_to_call(model):
            return model
    return None


def get_all_usage() -> dict:
    """
    Get usage stats for all tracked models.
    Returns: {model_id: {"used": int, "limit": int, "pct": float}}
    Used by the admin dashboard API.
    """
    stats = {}
    for model_id, limit in MODEL_DAILY_LIMITS.items():
        used = get_usage(model_id)
        stats[model_id] = {
            "used": used,
            "limit": limit,
            "pct": round(used / limit * 100, 1) if limit > 0 else 0,
            "safe": is_safe_to_call(model_id),
        }
    return stats
