# core/geocoder.py
# ═══════════════════════════════════════════════════════════
# Egyptian Address Geocoding with 3-Tier Fallback
# Google Maps → Nominatim (OSM) → OpenCage
# Handles freeform Arabic addresses, landmarks, Arabizi
# ═══════════════════════════════════════════════════════════
import os
import re
import json
import hashlib
import logging
import httpx

logger = logging.getLogger("fastdrop.geocoder")

# ── Cairo zone aliases (Arabic + English) ────────────────
CAIRO_ZONE_ALIASES = {
    "مصر الجديدة": "مصر الجديدة، القاهرة",
    "نصر": "مدينة نصر، القاهرة",
    "التجمع": "التجمع الخامس، القاهرة",
    "مدينة نصر": "مدينة نصر، القاهرة",
    "الزمالك": "الزمالك، القاهرة",
    "المعادي": "المعادي، القاهرة",
    "شبرا": "شبرا، القاهرة",
    "وسط البلد": "وسط البلد، القاهرة",
    "المهندسين": "المهندسين، القاهرة",
    "الدقي": "الدقي، القاهرة",
    "العباسية": "العباسية، القاهرة",
    "الهرم": "الهرم، الجيزة",
    "6 أكتوبر": "مدينة 6 أكتوبر، الجيزة",
    "الشيخ زايد": "الشيخ زايد، الجيزة",
    "العاشر": "العاشر من رمضان",
    # English aliases
    "downtown": "وسط البلد، القاهرة",
    "nasr city": "مدينة نصر، القاهرة",
    "maadi": "المعادي، القاهرة",
    "heliopolis": "مصر الجديدة، القاهرة",
    "zamalek": "الزمالك، القاهرة",
    "mohandessin": "المهندسين، القاهرة",
    "dokki": "الدقي، القاهرة",
    "new cairo": "التجمع الخامس، القاهرة",
    "6 october": "مدينة 6 أكتوبر، الجيزة",
    "sheikh zayed": "الشيخ زايد، الجيزة",
}


def normalize_address(raw: str) -> str:
    """
    Normalize Egyptian address before geocoding.
    Handles: Arabizi, abbreviations, zone aliases.
    """
    from core.arabic_normalizer import (
        detect_input_type,
        transliterate_arabizi,
        normalize_arabic,
    )

    # Step 1: Transliterate Arabizi
    if detect_input_type(raw) == "arabizi":
        raw = transliterate_arabizi(raw)

    # Step 2: Arabic text normalization
    raw = normalize_arabic(raw)

    # Step 3: Expand known zone aliases
    for alias, full in CAIRO_ZONE_ALIASES.items():
        raw = re.sub(re.escape(alias), full, raw, flags=re.IGNORECASE)

    # Step 4: Append Egypt/Cairo if no country reference
    if "مصر" not in raw and "egypt" not in raw.lower():
        raw = raw + "، القاهرة، مصر"

    return raw.strip()


# ═══════════════════════════════════════════════
# Primary: Google Maps Geocoding
# ═══════════════════════════════════════════════
async def geocode_google(address: str) -> dict | None:
    """Google Maps geocoding (10,000 free req/month)."""
    key = os.getenv("GOOGLE_MAPS_KEY")
    if not key:
        return None

    try:
        normalized = normalize_address(address)
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "address": normalized,
                    "language": "ar",
                    "region": "EG",
                    "key": key,
                },
            )
            data = r.json()
            if data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                loc_type = data["results"][0]["geometry"]["location_type"]
                return {
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "formatted": data["results"][0]["formatted_address"],
                    "accuracy": loc_type,
                    "provider": "google",
                    "confidence": 1.0
                    if loc_type in ["ROOFTOP", "RANGE_INTERPOLATED"]
                    else 0.7,
                }
    except Exception as e:
        logger.warning(f"[Geocode Google FAIL] {e}")
    return None


# ═══════════════════════════════════════════════
# Fallback 1: Nominatim (OpenStreetMap) — 100% free
# ═══════════════════════════════════════════════
async def geocode_nominatim(address: str) -> dict | None:
    """Nominatim geocoding — completely free, 1 req/sec limit."""
    try:
        normalized = normalize_address(address)
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": normalized,
                    "format": "json",
                    "countrycodes": "EG",
                    "accept-language": "ar",
                    "limit": 1,
                },
                headers={"User-Agent": "fastdrop_delivery/1.0"},
            )
            data = r.json()
            if data:
                return {
                    "lat": float(data[0]["lat"]),
                    "lng": float(data[0]["lon"]),
                    "formatted": data[0].get("display_name", ""),
                    "provider": "nominatim",
                    "confidence": 0.75,
                }
    except Exception as e:
        logger.warning(f"[Geocode Nominatim FAIL] {e}")
    return None


# ═══════════════════════════════════════════════
# Fallback 2: OpenCage — 2,500 free/day
# ═══════════════════════════════════════════════
async def geocode_opencage(address: str) -> dict | None:
    """OpenCage geocoding — 2,500 free req/day, no credit card."""
    key = os.getenv("OPENCAGE_API_KEY")
    if not key:
        return None

    try:
        normalized = normalize_address(address)
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.opencagedata.com/geocode/v1/json",
                params={
                    "q": normalized,
                    "key": key,
                    "language": "ar",
                    "countrycode": "eg",
                },
            )
            data = r.json()
            if data.get("results"):
                res = data["results"][0]
                return {
                    "lat": res["geometry"]["lat"],
                    "lng": res["geometry"]["lng"],
                    "formatted": res["formatted"],
                    "provider": "opencage",
                    "confidence": res.get("confidence", 5) / 10.0,
                }
    except Exception as e:
        logger.warning(f"[Geocode OpenCage FAIL] {e}")
    return None


# ═══════════════════════════════════════════════
# Master Geocoder with 3-Tier Fallback + Cache
# ═══════════════════════════════════════════════
async def geocode_address(raw_address: str) -> dict:
    """
    Geocode an Egyptian Arabic address with 3-tier fallback.
    Returns coords + confidence + provider name.
    Caches result in Redis for 30 days.
    """
    # Try Redis cache first
    try:
        import redis as redis_lib
        r_client = redis_lib.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        cache_key = f"geo:{hashlib.md5(raw_address.encode()).hexdigest()}"
        cached = r_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        r_client = None
        cache_key = None

    # Try providers in order: Google → Nominatim → OpenCage
    result = (
        await geocode_google(raw_address)
        or await geocode_nominatim(raw_address)
        or await geocode_opencage(raw_address)
    )

    if not result:
        raise ValueError(f"لم نتمكن من تحديد العنوان: {raw_address}")

    # Cache for 30 days
    if r_client and cache_key:
        try:
            r_client.setex(cache_key, 86400 * 30, json.dumps(result))
        except Exception:
            pass

    return result
