# core/zone_manager.py
# ═══════════════════════════════════════════════════════════
# Cairo Zone Manager — 25 Zones with Boundaries & Pricing
# Provides zone lookup by coordinates, pricing, capacity.
# ═══════════════════════════════════════════════════════════
import math
import logging

logger = logging.getLogger("fastdrop.zones")

# ═══════════════════════════════════════════════
# Cairo Zone Definitions
# ═══════════════════════════════════════════════
CAIRO_ZONES = [
    {
        "id": 1, "name_ar": "وسط البلد", "name_en": "Downtown",
        "center_lat": 30.0444, "center_lng": 31.2357,
        "radius_km": 2.0, "base_fee": 25.0, "max_daily": 300,
        "hours": ("08:00", "23:00"),
    },
    {
        "id": 2, "name_ar": "مدينة نصر", "name_en": "Nasr City",
        "center_lat": 30.0511, "center_lng": 31.3656,
        "radius_km": 4.0, "base_fee": 30.0, "max_daily": 250,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 3, "name_ar": "مصر الجديدة", "name_en": "Heliopolis",
        "center_lat": 30.0876, "center_lng": 31.3418,
        "radius_km": 3.0, "base_fee": 30.0, "max_daily": 200,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 4, "name_ar": "المعادي", "name_en": "Maadi",
        "center_lat": 29.9602, "center_lng": 31.2569,
        "radius_km": 3.5, "base_fee": 30.0, "max_daily": 200,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 5, "name_ar": "الزمالك", "name_en": "Zamalek",
        "center_lat": 30.0616, "center_lng": 31.2193,
        "radius_km": 1.5, "base_fee": 35.0, "max_daily": 150,
        "hours": ("09:00", "23:00"),
    },
    {
        "id": 6, "name_ar": "المهندسين", "name_en": "Mohandessin",
        "center_lat": 30.0560, "center_lng": 31.2010,
        "radius_km": 2.5, "base_fee": 30.0, "max_daily": 200,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 7, "name_ar": "الدقي", "name_en": "Dokki",
        "center_lat": 30.0381, "center_lng": 31.2075,
        "radius_km": 2.0, "base_fee": 28.0, "max_daily": 200,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 8, "name_ar": "التجمع الخامس", "name_en": "New Cairo (5th Settlement)",
        "center_lat": 30.0074, "center_lng": 31.4913,
        "radius_km": 6.0, "base_fee": 40.0, "max_daily": 250,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 9, "name_ar": "الشروق", "name_en": "El Shorouk",
        "center_lat": 30.1268, "center_lng": 31.6278,
        "radius_km": 4.0, "base_fee": 45.0, "max_daily": 150,
        "hours": ("09:00", "21:00"),
    },
    {
        "id": 10, "name_ar": "العبور", "name_en": "El Obour",
        "center_lat": 30.2342, "center_lng": 31.4865,
        "radius_km": 4.0, "base_fee": 45.0, "max_daily": 150,
        "hours": ("09:00", "21:00"),
    },
    {
        "id": 11, "name_ar": "شبرا", "name_en": "Shubra",
        "center_lat": 30.1081, "center_lng": 31.2444,
        "radius_km": 3.0, "base_fee": 25.0, "max_daily": 250,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 12, "name_ar": "العباسية", "name_en": "Abbassia",
        "center_lat": 30.0720, "center_lng": 31.2830,
        "radius_km": 2.0, "base_fee": 25.0, "max_daily": 200,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 13, "name_ar": "حلوان", "name_en": "Helwan",
        "center_lat": 29.8493, "center_lng": 31.3342,
        "radius_km": 4.0, "base_fee": 35.0, "max_daily": 150,
        "hours": ("09:00", "21:00"),
    },
    {
        "id": 14, "name_ar": "الهرم", "name_en": "Haram",
        "center_lat": 30.0131, "center_lng": 31.2089,
        "radius_km": 3.5, "base_fee": 30.0, "max_daily": 200,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 15, "name_ar": "فيصل", "name_en": "Faisal",
        "center_lat": 30.0167, "center_lng": 31.1833,
        "radius_km": 3.0, "base_fee": 28.0, "max_daily": 200,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 16, "name_ar": "6 أكتوبر", "name_en": "6th of October",
        "center_lat": 29.9792, "center_lng": 30.9267,
        "radius_km": 8.0, "base_fee": 50.0, "max_daily": 200,
        "hours": ("09:00", "21:00"),
    },
    {
        "id": 17, "name_ar": "الشيخ زايد", "name_en": "Sheikh Zayed",
        "center_lat": 30.0372, "center_lng": 30.9818,
        "radius_km": 5.0, "base_fee": 45.0, "max_daily": 180,
        "hours": ("09:00", "21:00"),
    },
    {
        "id": 18, "name_ar": "المقطم", "name_en": "Mokattam",
        "center_lat": 30.0155, "center_lng": 31.2900,
        "radius_km": 3.0, "base_fee": 30.0, "max_daily": 150,
        "hours": ("09:00", "21:00"),
    },
    {
        "id": 19, "name_ar": "مدينة السلام", "name_en": "Salam City",
        "center_lat": 30.1668, "center_lng": 31.3907,
        "radius_km": 3.5, "base_fee": 35.0, "max_daily": 150,
        "hours": ("09:00", "21:00"),
    },
    {
        "id": 20, "name_ar": "عين شمس", "name_en": "Ain Shams",
        "center_lat": 30.1312, "center_lng": 31.3285,
        "radius_km": 2.5, "base_fee": 25.0, "max_daily": 200,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 21, "name_ar": "المطرية", "name_en": "El Matariya",
        "center_lat": 30.1213, "center_lng": 31.3140,
        "radius_km": 2.0, "base_fee": 25.0, "max_daily": 180,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 22, "name_ar": "الرحاب", "name_en": "El Rehab",
        "center_lat": 30.0580, "center_lng": 31.4924,
        "radius_km": 2.5, "base_fee": 35.0, "max_daily": 150,
        "hours": ("09:00", "22:00"),
    },
    {
        "id": 23, "name_ar": "بدر", "name_en": "Badr City",
        "center_lat": 30.1391, "center_lng": 31.7162,
        "radius_km": 4.0, "base_fee": 50.0, "max_daily": 100,
        "hours": ("09:00", "20:00"),
    },
    {
        "id": 24, "name_ar": "العاشر من رمضان", "name_en": "10th of Ramadan",
        "center_lat": 30.2976, "center_lng": 31.7543,
        "radius_km": 6.0, "base_fee": 55.0, "max_daily": 120,
        "hours": ("09:00", "20:00"),
    },
    {
        "id": 25, "name_ar": "الجيزة", "name_en": "Giza",
        "center_lat": 30.0131, "center_lng": 31.2089,
        "radius_km": 4.0, "base_fee": 30.0, "max_daily": 250,
        "hours": ("09:00", "22:00"),
    },
]


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points using Haversine formula."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_zone_by_coords(lat: float, lng: float) -> dict | None:
    """
    Find the Cairo zone that contains the given coordinates.
    Returns zone dict or None if outside all zones.
    """
    best_zone = None
    best_distance = float("inf")

    for zone in CAIRO_ZONES:
        dist = _haversine_km(lat, lng, zone["center_lat"], zone["center_lng"])
        if dist <= zone["radius_km"] and dist < best_distance:
            best_zone = zone
            best_distance = dist

    return best_zone


def find_zone_by_name(name: str) -> dict | None:
    """Look up zone by Arabic or English name (case-insensitive)."""
    name_lower = name.lower().strip()
    for zone in CAIRO_ZONES:
        if (
            name_lower in zone["name_ar"]
            or name_lower == zone["name_en"].lower()
        ):
            return zone
    return None


def get_delivery_fee(
    pickup_lat: float,
    pickup_lng: float,
    delivery_lat: float,
    delivery_lng: float,
) -> float:
    """
    Calculate delivery fee based on zones and distance.
    Base fee from delivery zone + distance surcharge.
    """
    zone = find_zone_by_coords(delivery_lat, delivery_lng)
    base = zone["base_fee"] if zone else 40.0  # Default for unknown zones

    dist = _haversine_km(pickup_lat, pickup_lng, delivery_lat, delivery_lng)

    # Distance surcharge: 3 EGP per km after first 3 km
    surcharge = max(0, (dist - 3.0)) * 3.0

    return round(base + surcharge, 2)


def get_all_zones() -> list[dict]:
    """Return all active Cairo zones."""
    return CAIRO_ZONES


def is_within_service_area(lat: float, lng: float) -> bool:
    """Check if coordinates are within any serviced zone."""
    return find_zone_by_coords(lat, lng) is not None
