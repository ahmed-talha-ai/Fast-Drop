# ai/smart_features.py
# ═══════════════════════════════════════════════════════════════════
# Advanced AI Features — ETA, Demand, Fraud, Matching, Pricing,
# Sentiment, Behavior, Heatmap
# ═══════════════════════════════════════════════════════════════════
import logging
import math
import random
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger("fastdrop.ai.smart")


# ═══════════════════════════════════════════════
# 1. ETA Prediction
# ═══════════════════════════════════════════════

# Average speeds (km/h) by time of day in Cairo
CAIRO_SPEED_PROFILE = {
    "early_morning": 35,   # 5am-7am
    "morning_rush": 12,    # 7am-10am
    "midday": 22,          # 10am-1pm
    "afternoon": 18,       # 1pm-4pm
    "evening_rush": 10,    # 4pm-7pm
    "evening": 20,         # 7pm-10pm
    "night": 35,           # 10pm-5am
}

# Zone-specific traffic multipliers (1.0 = normal)
ZONE_TRAFFIC = {
    "Downtown": 1.5,       # Always congested
    "Nasr City": 1.2,
    "Heliopolis": 1.2,
    "Maadi": 1.0,
    "Zamalek": 1.3,
    "Mohandessin": 1.3,
    "Dokki": 1.3,
    "New Cairo (5th Settlement)": 0.8,  # Wide roads
    "El Shorouk": 0.7,
    "El Obour": 0.7,
    "Shubra": 1.4,
    "Abbassia": 1.3,
    "Helwan": 1.1,
    "Haram": 1.4,
    "Faisal": 1.4,
    "6th of October": 0.9,
    "Sheikh Zayed": 0.8,
    "Mokattam": 1.1,
    "Salam City": 1.0,
    "Ain Shams": 1.3,
    "El Matariya": 1.3,
    "El Rehab": 0.8,
    "Badr City": 0.7,
    "10th of Ramadan": 0.7,
    "Giza": 1.3,
    "New Administrative Capital": 0.6,  # Empty roads
}

# Day-of-week multipliers
DAY_MULTIPLIERS = {
    0: 1.0,   # Monday
    1: 1.0,   # Tuesday
    2: 1.0,   # Wednesday
    3: 1.05,  # Thursday (pre-weekend)
    4: 0.7,   # Friday (least traffic)
    5: 0.85,  # Saturday
    6: 1.1,   # Sunday (week start)
}


def _haversine_km(lat1, lng1, lat2, lng2):
    """Haversine distance in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_time_period(hour: int) -> str:
    """Map hour to traffic period."""
    if 5 <= hour < 7:
        return "early_morning"
    elif 7 <= hour < 10:
        return "morning_rush"
    elif 10 <= hour < 13:
        return "midday"
    elif 13 <= hour < 16:
        return "afternoon"
    elif 16 <= hour < 19:
        return "evening_rush"
    elif 19 <= hour < 22:
        return "evening"
    else:
        return "night"


def predict_eta(
    pickup_lat: float, pickup_lng: float,
    delivery_lat: float, delivery_lng: float,
    current_time: str | None = None,
    zone_name: str | None = None,
) -> dict:
    """
    Predict delivery ETA based on distance, time of day, zone traffic,
    and day of week.
    """
    now = datetime.fromisoformat(current_time) if current_time else datetime.now()

    # Distance
    distance_km = _haversine_km(pickup_lat, pickup_lng, delivery_lat, delivery_lng)

    # Base speed from time of day
    period = _get_time_period(now.hour)
    base_speed = CAIRO_SPEED_PROFILE[period]

    # Zone traffic multiplier
    zone_factor = ZONE_TRAFFIC.get(zone_name, 1.0) if zone_name else 1.0

    # Day of week factor
    day_factor = DAY_MULTIPLIERS.get(now.weekday(), 1.0)

    # Effective speed
    effective_speed = base_speed / (zone_factor * day_factor)

    # Travel time in minutes
    travel_minutes = (distance_km / effective_speed) * 60

    # Add preparation time (picking up, parking, etc.)
    prep_time = 10  # minutes for pickup
    delivery_time = 5  # minutes for handoff

    total_minutes = int(prep_time + travel_minutes + delivery_time)

    # Confidence based on how predictable the period is
    confidence_map = {
        "early_morning": 0.90, "morning_rush": 0.65,
        "midday": 0.80, "afternoon": 0.75,
        "evening_rush": 0.60, "evening": 0.85, "night": 0.90,
    }

    eta = now + timedelta(minutes=total_minutes)

    return {
        "estimated_minutes": total_minutes,
        "estimated_arrival": eta.isoformat(),
        "distance_km": round(distance_km, 2),
        "effective_speed_kmh": round(effective_speed, 1),
        "traffic_period": period,
        "traffic_period_ar": {
            "early_morning": "الصبح بدري",
            "morning_rush": "زحمة الصبح",
            "midday": "نص النهار",
            "afternoon": "بعد الضهر",
            "evening_rush": "زحمة المغرب",
            "evening": "بالليل",
            "night": "آخر الليل",
        }[period],
        "zone_traffic_factor": zone_factor,
        "confidence": confidence_map.get(period, 0.75),
        "breakdown": {
            "prep_minutes": prep_time,
            "travel_minutes": int(travel_minutes),
            "delivery_minutes": delivery_time,
        },
    }


# ═══════════════════════════════════════════════
# 2. Demand Forecasting
# ═══════════════════════════════════════════════

# Synthetic demand patterns per zone (orders per hour, typical weekday)
ZONE_DEMAND_PATTERNS = {
    "Downtown":       [0, 0, 0, 0, 0, 2, 5, 12, 18, 25, 20, 15, 22, 18, 15, 18, 25, 30, 22, 15, 8, 4, 2, 0],
    "Nasr City":      [0, 0, 0, 0, 0, 1, 3, 8,  15, 20, 18, 12, 18, 15, 12, 15, 20, 25, 18, 12, 6, 3, 1, 0],
    "Heliopolis":     [0, 0, 0, 0, 0, 1, 3, 8,  14, 18, 15, 11, 16, 14, 11, 13, 18, 22, 16, 10, 5, 2, 1, 0],
    "Maadi":          [0, 0, 0, 0, 0, 1, 2, 6,  12, 16, 14, 10, 14, 12, 10, 12, 16, 20, 14, 9,  4, 2, 1, 0],
    "6th of October": [0, 0, 0, 0, 0, 1, 2, 5,  10, 14, 12, 8,  12, 10, 8,  10, 14, 18, 12, 8,  4, 2, 1, 0],
    "New Cairo (5th Settlement)": [0,0,0,0,0,1,3,7,13,18,15,10,15,13,10,13,17,22,15,10,5,2,1,0],
    "Giza":           [0, 0, 0, 0, 0, 1, 3, 7,  12, 16, 14, 10, 14, 12, 10, 12, 16, 20, 14, 9,  4, 2, 1, 0],
    "Shubra":         [0, 0, 0, 0, 0, 1, 3, 8,  14, 18, 16, 11, 16, 13, 11, 13, 18, 22, 16, 10, 5, 2, 1, 0],
    "Haram":          [0, 0, 0, 0, 0, 1, 2, 6,  11, 15, 13, 9,  13, 11, 9,  11, 15, 19, 13, 8,  4, 2, 1, 0],
}

# Weekend/holiday multipliers
DEMAND_DAY_MULT = {
    0: 1.0,   # Mon
    1: 1.0,   # Tue
    2: 1.0,   # Wed
    3: 1.15,  # Thu (pre-weekend spike)
    4: 0.6,   # Fri (holiday)
    5: 0.8,   # Sat
    6: 1.1,   # Sun
}


def forecast_demand(
    zone_name: str | None = None,
    target_date: str | None = None,
    hours_ahead: int = 6,
) -> dict:
    """
    Forecast delivery demand by zone for the next N hours.
    Uses synthetic patterns with day-of-week adjustments.
    """
    now = datetime.fromisoformat(target_date) if target_date else datetime.now()
    day_mult = DEMAND_DAY_MULT.get(now.weekday(), 1.0)

    zones = [zone_name] if zone_name else list(ZONE_DEMAND_PATTERNS.keys())
    forecasts = {}

    for zone in zones:
        pattern = ZONE_DEMAND_PATTERNS.get(zone, [5] * 24)
        hourly = []

        for h_offset in range(hours_ahead):
            hour = (now.hour + h_offset) % 24
            base = pattern[hour]
            # Add some randomness (±15%)
            noise = random.uniform(0.85, 1.15)
            predicted = max(0, int(base * day_mult * noise))
            hourly.append({
                "hour": f"{hour:02d}:00",
                "predicted_orders": predicted,
            })

        total = sum(h["predicted_orders"] for h in hourly)
        peak_hour = max(hourly, key=lambda x: x["predicted_orders"])

        forecasts[zone] = {
            "hourly_forecast": hourly,
            "total_predicted": total,
            "peak_hour": peak_hour["hour"],
            "peak_orders": peak_hour["predicted_orders"],
            "recommended_drivers": max(1, total // 8),
        }

    return {
        "forecast_date": now.strftime("%Y-%m-%d"),
        "day_of_week": now.strftime("%A"),
        "day_multiplier": day_mult,
        "hours_ahead": hours_ahead,
        "zones": forecasts,
    }


# ═══════════════════════════════════════════════
# 3. Fraud / Anomaly Detection
# ═══════════════════════════════════════════════

# Normal ranges for order parameters
NORMAL_RANGES = {
    "weight_kg": {"min": 0.1, "max": 50, "critical_max": 200},
    "cod_amount": {"min": 0, "max": 5000, "critical_max": 20000},
    "distance_km": {"min": 0.1, "max": 80, "critical_max": 150},
}

# Known suspicious patterns
SUSPICIOUS_PATTERNS = [
    "same_address",        # Pickup = Delivery
    "excessive_weight",    # > 50kg
    "high_cod",           # > 5000 EGP
    "off_hours",          # Order outside working hours
    "rapid_orders",       # Same customer, many orders in short time
    "unreachable_area",   # Outside service zones
]


def check_anomaly(
    customer_id: int,
    pickup_lat: float, pickup_lng: float,
    delivery_lat: float, delivery_lng: float,
    weight_kg: float,
    cod_amount: float = 0,
    order_time: str | None = None,
    recent_order_count: int = 0,
) -> dict:
    """
    Check an order for suspicious patterns and anomalies.
    Returns risk score (0-100) and list of flags.
    """
    flags = []
    risk_score = 0
    now = datetime.fromisoformat(order_time) if order_time else datetime.now()

    # 1. Same address check
    dist = _haversine_km(pickup_lat, pickup_lng, delivery_lat, delivery_lng)
    if dist < 0.1:
        flags.append({
            "type": "same_address",
            "severity": "high",
            "message_ar": "عنوان الاستلام والتوصيل نفس المكان!",
            "message_en": "Pickup and delivery addresses are the same location",
        })
        risk_score += 40

    # 2. Excessive weight
    if weight_kg > NORMAL_RANGES["weight_kg"]["critical_max"]:
        flags.append({
            "type": "excessive_weight",
            "severity": "critical",
            "message_ar": f"وزن الطرد مبالغ فيه: {weight_kg} كجم",
            "message_en": f"Package weight is extreme: {weight_kg} kg",
        })
        risk_score += 35
    elif weight_kg > NORMAL_RANGES["weight_kg"]["max"]:
        flags.append({
            "type": "excessive_weight",
            "severity": "medium",
            "message_ar": f"وزن الطرد كبير: {weight_kg} كجم",
            "message_en": f"Package weight is high: {weight_kg} kg",
        })
        risk_score += 15

    # 3. High COD
    if cod_amount > NORMAL_RANGES["cod_amount"]["critical_max"]:
        flags.append({
            "type": "high_cod",
            "severity": "critical",
            "message_ar": f"مبلغ COD عالي جداً: {cod_amount} جنيه",
            "message_en": f"COD amount is extreme: {cod_amount} EGP",
        })
        risk_score += 35
    elif cod_amount > NORMAL_RANGES["cod_amount"]["max"]:
        flags.append({
            "type": "high_cod",
            "severity": "medium",
            "message_ar": f"مبلغ COD عالي: {cod_amount} جنيه",
            "message_en": f"COD amount exceeds normal limit: {cod_amount} EGP",
        })
        risk_score += 15

    # 4. Off-hours order
    if now.hour < 6 or now.hour > 23:
        flags.append({
            "type": "off_hours",
            "severity": "low",
            "message_ar": "الأوردر في وقت متأخر — خارج ساعات العمل",
            "message_en": f"Order placed at unusual hour: {now.hour}:00",
        })
        risk_score += 10

    # 5. Rapid orders (velocity check)
    if recent_order_count > 10:
        flags.append({
            "type": "rapid_orders",
            "severity": "high",
            "message_ar": f"العميل عمل {recent_order_count} أوردر في وقت قصير",
            "message_en": f"Customer placed {recent_order_count} orders rapidly",
        })
        risk_score += 25

    # 6. Excessive distance
    if dist > NORMAL_RANGES["distance_km"]["critical_max"]:
        flags.append({
            "type": "unreachable_area",
            "severity": "high",
            "message_ar": f"المسافة بعيدة جداً: {dist:.1f} كم",
            "message_en": f"Distance is extreme: {dist:.1f} km",
        })
        risk_score += 25
    elif dist > NORMAL_RANGES["distance_km"]["max"]:
        flags.append({
            "type": "long_distance",
            "severity": "medium",
            "message_ar": f"المسافة طويلة: {dist:.1f} كم",
            "message_en": f"Distance is far: {dist:.1f} km",
        })
        risk_score += 10

    # Determine risk level
    risk_score = min(risk_score, 100)
    if risk_score >= 70:
        risk_level = "critical"
        action_ar = "إيقاف الأوردر للمراجعة اليدوية"
    elif risk_score >= 40:
        risk_level = "high"
        action_ar = "مطلوب مراجعة — تحقق من العميل"
    elif risk_score >= 20:
        risk_level = "medium"
        action_ar = "تنبيه بسيط — راقب العميل"
    else:
        risk_level = "low"
        action_ar = "عادي — مفيش مشاكل"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "flags": flags,
        "flag_count": len(flags),
        "action_ar": action_ar,
        "distance_km": round(dist, 2),
    }


# ═══════════════════════════════════════════════
# 4. Smart Driver Matching
# ═══════════════════════════════════════════════

def match_driver(
    order: dict,
    drivers: list[dict],
) -> dict:
    """
    Score and rank all available drivers for an order using
    multi-factor scoring: proximity, performance, capacity, workload.

    Weights:
        - Proximity: 35% (closer = better)
        - Performance: 25% (higher score = better)
        - Capacity: 20% (can carry the package)
        - Workload: 20% (fewer current orders = better)
    """
    if not drivers:
        return {"matched": False, "reason": "No available drivers"}

    order_lat = order.get("lat", 30.044)
    order_lng = order.get("lng", 31.235)
    order_weight = order.get("weight_kg", 1.0)

    scored_drivers = []

    for driver in drivers:
        d_lat = driver.get("lat", order_lat)
        d_lng = driver.get("lng", order_lng)

        # 1. Proximity score (0-1, closer = higher)
        dist = _haversine_km(order_lat, order_lng, d_lat, d_lng)
        max_dist = 30.0  # km
        proximity = max(0, 1 - (dist / max_dist))

        # 2. Performance score (0-1)
        performance = driver.get("performance_score", 0.8)

        # 3. Capacity score (binary + bonus for right vehicle)
        max_weight = driver.get("max_weight_kg", 20.0)
        if order_weight > max_weight:
            capacity = 0.0  # Can't carry
        else:
            capacity = 1.0 - (order_weight / max_weight) * 0.5

        # 4. Workload score (fewer current orders = higher)
        current_orders = driver.get("current_orders", 0)
        max_orders = 15
        workload = max(0, 1 - (current_orders / max_orders))

        # Weighted total
        total = (
            0.35 * proximity +
            0.25 * performance +
            0.20 * capacity +
            0.20 * workload
        )

        scored_drivers.append({
            "driver_id": driver["id"],
            "driver_name": driver.get("name", "Unknown"),
            "total_score": round(total, 4),
            "distance_km": round(dist, 2),
            "scores": {
                "proximity": round(proximity, 3),
                "performance": round(performance, 3),
                "capacity": round(capacity, 3),
                "workload": round(workload, 3),
            },
            "can_carry": order_weight <= max_weight,
            "vehicle_type": driver.get("vehicle_type", "motorcycle"),
        })

    # Sort by total score descending
    scored_drivers.sort(key=lambda d: d["total_score"], reverse=True)

    # Filter out drivers who can't carry
    eligible = [d for d in scored_drivers if d["can_carry"]]

    best = eligible[0] if eligible else None

    return {
        "matched": best is not None,
        "best_driver": best,
        "all_rankings": scored_drivers[:10],
        "eligible_count": len(eligible),
        "total_evaluated": len(scored_drivers),
    }


# ═══════════════════════════════════════════════
# 5. Dynamic Pricing
# ═══════════════════════════════════════════════

# Base fees per zone (EGP)
BASE_FEES = {
    "Downtown": 25, "Nasr City": 30, "Heliopolis": 30,
    "Maadi": 30, "Zamalek": 35, "Mohandessin": 30,
    "Dokki": 28, "New Cairo (5th Settlement)": 40,
    "El Shorouk": 45, "El Obour": 45, "Shubra": 25,
    "Abbassia": 25, "Helwan": 35, "Haram": 30,
    "Faisal": 28, "6th of October": 50, "Sheikh Zayed": 45,
    "Mokattam": 30, "Salam City": 35, "Ain Shams": 25,
    "El Matariya": 25, "El Rehab": 35, "Badr City": 50,
    "10th of Ramadan": 55, "Giza": 30,
    "New Administrative Capital": 65,
}


def calculate_dynamic_price(
    pickup_lat: float, pickup_lng: float,
    delivery_lat: float, delivery_lng: float,
    weight_kg: float = 1.0,
    cod_amount: float = 0.0,
    zone_name: str | None = None,
    current_time: str | None = None,
    demand_level: str = "normal",  # low, normal, high, surge
) -> dict:
    """
    Calculate delivery fee with dynamic pricing.

    Factors: base fee + distance + weight + time surcharge +
    demand multiplier + COD fee.
    """
    now = datetime.fromisoformat(current_time) if current_time else datetime.now()

    # Base fee
    base_fee = BASE_FEES.get(zone_name, 30.0)

    # Distance fee: 3 EGP per km after first 3 km
    distance_km = _haversine_km(pickup_lat, pickup_lng, delivery_lat, delivery_lng)
    distance_fee = max(0, (distance_km - 3) * 3)

    # Weight fee: 2 EGP per kg after first 5 kg
    weight_fee = max(0, (weight_kg - 5) * 2)

    # Time surcharge
    period = _get_time_period(now.hour)
    time_surcharges = {
        "early_morning": 0, "morning_rush": 10,
        "midday": 0, "afternoon": 5,
        "evening_rush": 15, "evening": 5, "night": 20,
    }
    time_surcharge = time_surcharges.get(period, 0)

    # Demand multiplier
    demand_multipliers = {
        "low": 0.9,      # 10% discount
        "normal": 1.0,
        "high": 1.25,    # 25% surge
        "surge": 1.5,    # 50% surge (peak demand)
    }
    demand_mult = demand_multipliers.get(demand_level, 1.0)

    # Holiday/Friday surcharge
    day_surcharge = 0
    if now.weekday() == 4:  # Friday
        day_surcharge = 10
    elif now.weekday() == 3:  # Thursday night
        if now.hour >= 18:
            day_surcharge = 5

    # COD fee (2% of COD amount)
    cod_fee = cod_amount * 0.02

    # Calculate total
    subtotal = base_fee + distance_fee + weight_fee + time_surcharge + day_surcharge
    surged_total = subtotal * demand_mult
    final_total = surged_total + cod_fee

    # Discount for long distance (loyalty)
    discount = 0
    if distance_km > 20:
        discount = final_total * 0.05  # 5% off
        final_total -= discount

    return {
        "final_fee": round(final_total, 2),
        "currency": "EGP",
        "breakdown": {
            "base_fee": base_fee,
            "distance_fee": round(distance_fee, 2),
            "weight_fee": round(weight_fee, 2),
            "time_surcharge": time_surcharge,
            "day_surcharge": day_surcharge,
            "demand_multiplier": demand_mult,
            "cod_fee": round(cod_fee, 2),
            "discount": round(discount, 2),
        },
        "distance_km": round(distance_km, 2),
        "demand_level": demand_level,
        "traffic_period": period,
        "demand_level_ar": {
            "low": "طلب منخفض — خصم 10%",
            "normal": "طلب عادي",
            "high": "طلب عالي — زيادة 25%",
            "surge": "ذروة الطلب — زيادة 50%",
        }.get(demand_level, "عادي"),
    }


# ═══════════════════════════════════════════════
# 6. Customer Sentiment Analysis
# ═══════════════════════════════════════════════

# Arabic sentiment keywords
POSITIVE_KEYWORDS_AR = [
    "شكرا", "ممتاز", "رائع", "حلو", "تمام", "عظيم", "برافو",
    "الله ينور", "ربنا يباركلك", "أحسن", "مبسوط", "جميل",
    "سريع", "كويس", "حبيبي", "يسلمو", "شغل نضيف", "بارك الله",
    "thank", "great", "perfect", "amazing", "good", "excellent",
    "fast", "wonderful", "happy", "best", "awesome", "love",
]

NEGATIVE_KEYWORDS_AR = [
    "زبالة", "وحش", "سيء", "فاشل", "تعبان", "زعلان", "متأخر",
    "مشكلة", "شكوى", "خرب", "اتكسر", "اتسرق", "ضايع", "مش موجود",
    "فين", "عايز فلوسي", "حرامي", "نصاب", "اسوأ", "ماجاش",
    "bad", "terrible", "worst", "late", "broken", "stolen",
    "missing", "angry", "complaint", "refund", "scam", "awful",
]

URGENT_KEYWORDS = [
    "عاجل", "ضروري", "فوراً", "دلوقتي", "حالاً", "urgent",
    "asap", "emergency", "immediately", "now", "critical",
    "مستنيك", "محتاجه", "محتاج",
]


def analyze_sentiment(message: str) -> dict:
    """
    Analyze customer message sentiment using keyword matching
    with weighted scoring.
    """
    msg_lower = message.lower()

    pos_matches = [kw for kw in POSITIVE_KEYWORDS_AR if kw in msg_lower]
    neg_matches = [kw for kw in NEGATIVE_KEYWORDS_AR if kw in msg_lower]
    urgent_matches = [kw for kw in URGENT_KEYWORDS if kw in msg_lower]

    pos_score = len(pos_matches) * 2
    neg_score = len(neg_matches) * 3  # Negative weighs more
    urgent_score = len(urgent_matches) * 2

    # Net sentiment (-1.0 to 1.0)
    total = pos_score + neg_score + 1  # avoid div by zero
    sentiment_score = (pos_score - neg_score) / total
    sentiment_score = max(-1.0, min(1.0, sentiment_score))

    # Classify
    if sentiment_score > 0.3:
        sentiment = "positive"
        sentiment_ar = "😊 العميل مبسوط"
        priority = "normal"
    elif sentiment_score < -0.3:
        sentiment = "negative"
        sentiment_ar = "😠 العميل زعلان"
        priority = "high"
    else:
        sentiment = "neutral"
        sentiment_ar = "😐 رسالة عادية"
        priority = "normal"

    # Urgency override
    is_urgent = len(urgent_matches) > 0
    if is_urgent:
        priority = "urgent"

    return {
        "sentiment": sentiment,
        "sentiment_ar": sentiment_ar,
        "sentiment_score": round(sentiment_score, 3),
        "priority": priority,
        "is_urgent": is_urgent,
        "positive_keywords": pos_matches,
        "negative_keywords": neg_matches,
        "urgent_keywords": urgent_matches,
        "recommended_action_ar": {
            "positive": "رد عادي — العميل راضي",
            "negative": "تصعيد فوري — العميل محتاج مساعدة سريعة",
            "neutral": "رد عادي — استفسار عادي",
        }.get(sentiment, "رد عادي"),
    }


# ═══════════════════════════════════════════════
# 7. Driver Behavior Analysis
# ═══════════════════════════════════════════════

def analyze_driver_behavior(
    driver_id: int,
    deliveries_completed: int = 0,
    deliveries_failed: int = 0,
    avg_delivery_time_min: float = 30,
    cancellation_count: int = 0,
    customer_complaints: int = 0,
    avg_rating: float = 4.5,
    days_active: int = 30,
    total_distance_km: float = 500,
) -> dict:
    """
    Analyze driver behavior patterns and generate insights.
    """
    total = deliveries_completed + deliveries_failed

    # Metrics
    success_rate = (deliveries_completed / max(total, 1)) * 100
    cancel_rate = (cancellation_count / max(total, 1)) * 100
    complaint_rate = (customer_complaints / max(deliveries_completed, 1)) * 100
    daily_avg = deliveries_completed / max(days_active, 1)
    avg_distance = total_distance_km / max(deliveries_completed, 1)

    # Behavior patterns
    patterns = []

    # Speed patterns
    if avg_delivery_time_min < 20:
        patterns.append({
            "type": "fast_deliverer",
            "label_ar": "🏎️ سواق سريع — بيوصل في وقت قياسي",
            "label_en": "Fast deliverer — consistently quick",
            "impact": "positive",
        })
    elif avg_delivery_time_min > 50:
        patterns.append({
            "type": "slow_deliverer",
            "label_ar": "🐌 بطيء في التوصيل — محتاج متابعة",
            "label_en": "Slow deliverer — needs monitoring",
            "impact": "negative",
        })

    # Reliability
    if success_rate >= 95:
        patterns.append({
            "type": "reliable",
            "label_ar": "⭐ سواق موثوق — نسبة نجاح عالية",
            "label_en": "Highly reliable driver",
            "impact": "positive",
        })
    elif success_rate < 80:
        patterns.append({
            "type": "unreliable",
            "label_ar": "⚠️ نسبة فشل عالية — محتاج تدريب",
            "label_en": "High failure rate — needs training",
            "impact": "negative",
        })

    # Cancellation pattern
    if cancel_rate > 10:
        patterns.append({
            "type": "high_cancellation",
            "label_ar": "🚫 بيكنسل كتير — فيه مشكلة",
            "label_en": "High cancellation rate",
            "impact": "negative",
        })

    # Complaint pattern
    if complaint_rate > 5:
        patterns.append({
            "type": "complaints",
            "label_ar": "📢 شكاوى كتيرة — محتاج مراجعة",
            "label_en": "High complaint rate",
            "impact": "negative",
        })
    elif complaint_rate == 0 and deliveries_completed > 50:
        patterns.append({
            "type": "zero_complaints",
            "label_ar": "🏆 صفر شكاوى — أداء مثالي",
            "label_en": "Zero complaints — exemplary service",
            "impact": "positive",
        })

    # Volume patterns
    if daily_avg >= 15:
        patterns.append({
            "type": "high_volume",
            "label_ar": "📦 بيشتغل كتير — حجم توصيل عالي",
            "label_en": "High volume deliverer",
            "impact": "positive",
        })

    # Rating
    if avg_rating >= 4.8:
        patterns.append({
            "type": "top_rated",
            "label_ar": "🌟 تقييم ممتاز من العملاء",
            "label_en": "Top-rated by customers",
            "impact": "positive",
        })

    positive = len([p for p in patterns if p["impact"] == "positive"])
    negative = len([p for p in patterns if p["impact"] == "negative"])

    if positive > negative:
        overall = "excellent"
        overall_ar = "⭐ أداء ممتاز — يستحق مكافأة"
    elif negative > positive:
        overall = "needs_improvement"
        overall_ar = "⚠️ محتاج تحسين — مطلوب متابعة"
    else:
        overall = "average"
        overall_ar = "😐 أداء متوسط — عادي"

    return {
        "driver_id": driver_id,
        "overall_assessment": overall,
        "overall_assessment_ar": overall_ar,
        "metrics": {
            "success_rate": round(success_rate, 1),
            "cancel_rate": round(cancel_rate, 1),
            "complaint_rate": round(complaint_rate, 1),
            "avg_delivery_time_min": round(avg_delivery_time_min, 1),
            "daily_average": round(daily_avg, 1),
            "avg_distance_km": round(avg_distance, 2),
            "total_deliveries": total,
            "rating": avg_rating,
        },
        "patterns": patterns,
        "positive_count": positive,
        "negative_count": negative,
        "recommendations_ar": _get_recommendations_ar(patterns),
    }


def _get_recommendations_ar(patterns: list[dict]) -> list[str]:
    """Generate Arabic recommendations based on patterns."""
    recs = []
    types = [p["type"] for p in patterns]
    if "slow_deliverer" in types:
        recs.append("📍 تأكد إن السواق بيستخدم GPS ومش بيضيع وقت")
    if "unreliable" in types:
        recs.append("🎓 محتاج تدريب على التعامل مع العملاء والعناوين")
    if "high_cancellation" in types:
        recs.append("📞 اعرف سبب الكنسلة — ممكن يكون فيه مشاكل في العناوين")
    if "complaints" in types:
        recs.append("👂 راجع الشكاوى واتكلم مع السواق عن التحسين")
    if "top_rated" in types:
        recs.append("🏆 يستحق مكافأة أو ترقية للأوردرات المميزة")
    if "high_volume" in types:
        recs.append("💰 فكّر تديله حوافز إضافية عشان الالتزام")
    if not recs:
        recs.append("👍 استمر كده — أداء كويس")
    return recs


# ═══════════════════════════════════════════════
# 8. Zone Heatmap
# ═══════════════════════════════════════════════

ZONE_COORDS = {
    "Downtown":       {"lat": 30.0444, "lng": 31.2357},
    "Nasr City":      {"lat": 30.0511, "lng": 31.3656},
    "Heliopolis":     {"lat": 30.0876, "lng": 31.3418},
    "Maadi":          {"lat": 29.9602, "lng": 31.2569},
    "Zamalek":        {"lat": 30.0616, "lng": 31.2193},
    "Mohandessin":    {"lat": 30.0560, "lng": 31.2010},
    "Dokki":          {"lat": 30.0381, "lng": 31.2075},
    "New Cairo (5th Settlement)": {"lat": 30.0074, "lng": 31.4913},
    "El Shorouk":     {"lat": 30.1268, "lng": 31.6278},
    "El Obour":       {"lat": 30.2342, "lng": 31.4865},
    "Shubra":         {"lat": 30.1081, "lng": 31.2444},
    "Abbassia":       {"lat": 30.0720, "lng": 31.2830},
    "Helwan":         {"lat": 29.8493, "lng": 31.3342},
    "Haram":          {"lat": 30.0131, "lng": 31.2089},
    "Faisal":         {"lat": 30.0167, "lng": 31.1833},
    "6th of October": {"lat": 29.9792, "lng": 30.9267},
    "Sheikh Zayed":   {"lat": 30.0372, "lng": 30.9818},
    "Mokattam":       {"lat": 30.0155, "lng": 31.2900},
    "Salam City":     {"lat": 30.1668, "lng": 31.3907},
    "Ain Shams":      {"lat": 30.1312, "lng": 31.3285},
    "El Matariya":    {"lat": 30.1213, "lng": 31.3140},
    "El Rehab":       {"lat": 30.0580, "lng": 31.4924},
    "Badr City":      {"lat": 30.1391, "lng": 31.7162},
    "10th of Ramadan": {"lat": 30.2976, "lng": 31.7543},
    "Giza":           {"lat": 30.0131, "lng": 31.2089},
    "New Administrative Capital": {"lat": 30.0196, "lng": 31.7625},
}


def generate_zone_heatmap(
    current_time: str | None = None,
    include_forecast: bool = True,
) -> dict:
    """
    Generate zone-based order density heatmap.
    Uses demand patterns to color-code zones by activity level.
    """
    now = datetime.fromisoformat(current_time) if current_time else datetime.now()
    hour = now.hour
    day_mult = DEMAND_DAY_MULT.get(now.weekday(), 1.0)

    zones_data = []

    for zone_name, coords in ZONE_COORDS.items():
        pattern = ZONE_DEMAND_PATTERNS.get(zone_name, [5] * 24)
        current_demand = int(pattern[hour] * day_mult)
        peak_demand = max(pattern)
        intensity = current_demand / max(peak_demand, 1)

        # Determine heat level
        if intensity >= 0.8:
            heat = "hot"
            color = "#FF0000"
            label_ar = "🔴 نشاط عالي جداً"
        elif intensity >= 0.5:
            heat = "warm"
            color = "#FFA500"
            label_ar = "🟠 نشاط متوسط لعالي"
        elif intensity >= 0.3:
            heat = "mild"
            color = "#FFFF00"
            label_ar = "🟡 نشاط متوسط"
        elif intensity > 0:
            heat = "cool"
            color = "#00FF00"
            label_ar = "🟢 نشاط منخفض"
        else:
            heat = "inactive"
            color = "#808080"
            label_ar = "⚪ مفيش نشاط"

        zone_data = {
            "zone_name": zone_name,
            "lat": coords["lat"],
            "lng": coords["lng"],
            "current_orders": current_demand,
            "intensity": round(intensity, 2),
            "heat_level": heat,
            "color": color,
            "label_ar": label_ar,
            "recommended_drivers": max(1, current_demand // 5),
        }

        # Add next hour forecast
        if include_forecast:
            next_hour = (hour + 1) % 24
            next_demand = int(pattern[next_hour] * day_mult)
            trend = "increasing" if next_demand > current_demand else \
                    "decreasing" if next_demand < current_demand else "stable"
            zone_data["forecast"] = {
                "next_hour_orders": next_demand,
                "trend": trend,
                "trend_ar": {
                    "increasing": "📈 هيزيد",
                    "decreasing": "📉 هيقل",
                    "stable": "➡️ ثابت",
                }[trend],
            }

        zones_data.append(zone_data)

    # Sort by intensity descending
    zones_data.sort(key=lambda z: z["intensity"], reverse=True)

    # Summary
    hot_zones = [z["zone_name"] for z in zones_data if z["heat_level"] == "hot"]
    total_demand = sum(z["current_orders"] for z in zones_data)

    return {
        "timestamp": now.isoformat(),
        "hour": hour,
        "total_active_zones": len([z for z in zones_data if z["current_orders"] > 0]),
        "total_demand": total_demand,
        "hottest_zones": hot_zones[:5],
        "recommended_total_drivers": max(3, total_demand // 5),
        "zones": zones_data,
    }
