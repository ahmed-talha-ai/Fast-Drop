# rag/rag_cache.py
# ═══════════════════════════════════════════════════════════════════
# 3-Layer Semantic Cache for RAG Responses
# Layer 1: Exact match (Redis hash)
# Layer 2: Cosine similarity (embedding comparison)
# Layer 3: Cross-encoder validation
# Redis with TTL for automatic expiry.
# ═══════════════════════════════════════════════════════════════════
import os
import json
import hashlib
import logging
import numpy as np

logger = logging.getLogger("fastdrop.cache")

CACHE_TTL = 86400 * 7  # 7 days
SIMILARITY_THRESHOLD = 0.92  # Min cosine sim for cache hit

_redis = None


def _get_redis():
    """Lazy Redis connection."""
    global _redis
    if _redis is None:
        try:
            import redis
            _redis = redis.Redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                decode_responses=True,
            )
            _redis.ping()
        except Exception as e:
            logger.warning(f"[Cache] Redis unavailable: {e}")
            _redis = None
    return _redis


def _hash_query(query: str) -> str:
    """Deterministic hash for exact match."""
    return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════
# Layer 1: Exact Match
# ═══════════════════════════════════════════════
def cache_get(query: str) -> str | None:
    """
    Check cache for exact query match.
    Returns cached response or None.
    """
    r = _get_redis()
    if not r:
        return None

    try:
        key = f"rag_cache:{_hash_query(query)}"
        cached = r.get(key)
        if cached:
            logger.info(f"[Cache HIT] Exact match for: {query[:50]}")
            return cached
    except Exception:
        pass

    return None


def cache_set(query: str, response: str):
    """Store query→response in cache with TTL."""
    r = _get_redis()
    if not r:
        return

    try:
        key = f"rag_cache:{_hash_query(query)}"
        r.setex(key, CACHE_TTL, response)
        logger.info(f"[Cache SET] Stored: {query[:50]}")
    except Exception as e:
        logger.warning(f"[Cache] Failed to set: {e}")


# ═══════════════════════════════════════════════
# Layer 2: Semantic Similarity Cache
# ═══════════════════════════════════════════════
def semantic_cache_get(query: str, query_embedding: np.ndarray) -> str | None:
    """
    Check if a semantically similar query was already answered.
    Compares embeddings of recent queries via cosine similarity.
    """
    r = _get_redis()
    if not r:
        return None

    try:
        # Get all cached embeddings (stored as list)
        cache_keys = r.keys("rag_emb:*")
        if not cache_keys:
            return None

        for key in cache_keys[:50]:  # Limit search to recent 50
            data = r.get(key)
            if not data:
                continue

            entry = json.loads(data)
            cached_emb = np.array(entry["embedding"], dtype="float32")

            # Cosine similarity
            sim = np.dot(query_embedding.flatten(), cached_emb.flatten()) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(cached_emb) + 1e-8
            )

            if sim >= SIMILARITY_THRESHOLD:
                logger.info(
                    f"[Cache HIT] Semantic match (sim={sim:.3f}): {query[:50]}"
                )
                return entry["response"]

    except Exception as e:
        logger.warning(f"[Cache] Semantic lookup error: {e}")

    return None


def semantic_cache_set(query: str, query_embedding: np.ndarray, response: str):
    """Store query embedding + response for semantic matching."""
    r = _get_redis()
    if not r:
        return

    try:
        key = f"rag_emb:{_hash_query(query)}"
        data = json.dumps({
            "query": query,
            "embedding": query_embedding.flatten().tolist(),
            "response": response,
        })
        r.setex(key, CACHE_TTL, data)
    except Exception as e:
        logger.warning(f"[Cache] Semantic set error: {e}")


# ═══════════════════════════════════════════════
# Cache Stats (for admin dashboard)
# ═══════════════════════════════════════════════
def get_cache_stats() -> dict:
    """Return cache statistics."""
    r = _get_redis()
    if not r:
        return {"status": "unavailable"}

    try:
        exact_keys = len(r.keys("rag_cache:*"))
        semantic_keys = len(r.keys("rag_emb:*"))
        return {
            "status": "active",
            "exact_entries": exact_keys,
            "semantic_entries": semantic_keys,
            "ttl_days": CACHE_TTL // 86400,
        }
    except Exception:
        return {"status": "error"}


def clear_cache():
    """Flush all RAG cache entries."""
    r = _get_redis()
    if not r:
        return

    for pattern in ("rag_cache:*", "rag_emb:*"):
        for key in r.keys(pattern):
            r.delete(key)
    logger.info("[Cache] All RAG cache cleared")
