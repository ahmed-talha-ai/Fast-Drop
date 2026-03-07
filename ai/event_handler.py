# ai/event_handler.py
# ═══════════════════════════════════════════════════════════════════
# Real-Time Event Handler — Celery Workers
# Monitors shipments, detects delays, triggers re-routing,
# generates Arabic alerts for drivers and customers.
# ═══════════════════════════════════════════════════════════════════
import os
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("fastdrop.events")

# ═══════════════════════════════════════════════
# Celery Setup (deferred to avoid import errors when Redis is down)
# ═══════════════════════════════════════════════
_celery_app = None


def get_celery():
    global _celery_app
    if _celery_app is None:
        from celery import Celery
        _celery_app = Celery(
            "fastdrop",
            broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            backend=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
        )
        _celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="Africa/Cairo",
            enable_utc=True,
            task_soft_time_limit=300,
            task_time_limit=600,
        )
    return _celery_app


# ═══════════════════════════════════════════════
# Event Types
# ═══════════════════════════════════════════════
EVENT_TYPES = {
    "shipment_delayed": "تأخير في التوصيل",
    "traffic_detected": "ازدحام مروري",
    "driver_idle": "السواق واقف",
    "delivery_failed": "فشل التوصيل",
    "out_of_zone": "خارج منطقة الخدمة",
    "reroute_needed": "محتاج إعادة توجيه",
}


# ═══════════════════════════════════════════════
# Delay Detection
# ═══════════════════════════════════════════════
def detect_delay(
    current_time: datetime,
    estimated_arrival: datetime,
    actual_progress_pct: float,
    expected_progress_pct: float,
) -> dict:
    """
    Detect if a shipment is delayed based on progress vs. expectations.
    Returns delay dict with severity and estimated extra time.
    """
    time_remaining = (estimated_arrival - current_time).total_seconds() / 60
    progress_gap = expected_progress_pct - actual_progress_pct

    if progress_gap < 0.1 or time_remaining > 30:
        return {"delayed": False}

    # Estimate delay severity
    if progress_gap > 0.4:
        severity = "critical"  # >40% behind
        extra_minutes = int(time_remaining * progress_gap * 2)
    elif progress_gap > 0.2:
        severity = "major"     # 20-40% behind
        extra_minutes = int(time_remaining * progress_gap * 1.5)
    else:
        severity = "minor"     # 10-20% behind
        extra_minutes = int(time_remaining * progress_gap)

    return {
        "delayed": True,
        "severity": severity,
        "extra_minutes": extra_minutes,
        "progress_gap_pct": round(progress_gap * 100, 1),
    }


# ═══════════════════════════════════════════════
# Arabic Alert Generation
# ═══════════════════════════════════════════════
def generate_customer_alert_arabic(order_id: str, delay_info: dict) -> str:
    """Generate customer-facing delay alert in Egyptian Arabic."""
    severity = delay_info.get("severity", "minor")
    extra = delay_info.get("extra_minutes", 15)

    if severity == "critical":
        return (
            f"🚨 أوردر #{order_id}\n"
            f"أحنا آسفين جداً — في تأخير كبير ~{extra} دقيقة. "
            f"الفريق بتاعنا شغال عليه دلوقتي وهنحاول نوصله بأسرع وقت. "
            f"لو محتاج تعدل الموعد كلمنا."
        )
    elif severity == "major":
        return (
            f"⚠️ أوردر #{order_id}\n"
            f"حصل تأخير بسيط ~{extra} دقيقة بسبب الزحمة. "
            f"الأوردر لسه في الطريق وهيوصلك إن شاء الله."
        )
    else:
        return (
            f"📦 أوردر #{order_id}\n"
            f"الأوردر في الطريق — ممكن يتأخر {extra} دقيقة بسيطين. "
            f"شكراً لصبرك! 😊"
        )


def generate_driver_alert_arabic(delay_info: dict, new_route: list = None) -> str:
    """Generate driver-facing alert in Egyptian Arabic."""
    severity = delay_info.get("severity", "minor")

    if new_route:
        return (
            f"🔄 في تحديث للمسار بتاعك!\n"
            f"بسبب الزحمة اتغير الترتيب. "
            f"الستوب الجاي: {new_route[0].get('address', 'شوف الخريطة')}.\n"
            f"اضغط هنا للمسار الجديد. 👆"
        )
    if severity in ("critical", "major"):
        return (
            f"⚡ انتبه! في تأخير {delay_info.get('extra_minutes', 0)} دقيقة.\n"
            f"حاول تتجنب الزحمة لو تقدر."
        )
    return ""


# ═══════════════════════════════════════════════
# Re-Routing (LLM-assisted for major delays)
# ═══════════════════════════════════════════════
def suggest_reroute(
    remaining_stops: list[dict],
    current_lat: float,
    current_lng: float,
) -> list[dict]:
    """
    Re-optimize remaining stops from current driver position.
    Uses OR-Tools VRP for computation.
    """
    if not remaining_stops:
        return []

    from ai.clustering import optimize_route_vrp

    orders = [
        {
            "id": s.get("order_id", s.get("id")),
            "lat": s["lat"],
            "lng": s["lng"],
            "weight_kg": s.get("weight_kg", 1.0),
        }
        for s in remaining_stops
    ]

    new_route = optimize_route_vrp(
        orders,
        depot_lat=current_lat,
        depot_lng=current_lng,
    )
    logger.info(f"[Reroute] {len(new_route)} stops re-optimized from driver position")
    return new_route


# ═══════════════════════════════════════════════
# Celery Tasks
# ═══════════════════════════════════════════════
def monitor_shipment_task(shipment_data: dict):
    """
    Celery task: Check single shipment for delays.
    Called periodically by Celery Beat or the main API.
    """
    celery = get_celery()

    @celery.task(name="fastdrop.monitor_shipment")
    def _monitor(data):
        now = datetime.now()
        eta = datetime.fromisoformat(data.get("eta", now.isoformat()))
        progress = data.get("actual_progress_pct", 0.5)
        expected = data.get("expected_progress_pct", 0.5)

        delay = detect_delay(now, eta, progress, expected)

        if delay["delayed"]:
            logger.warning(
                f"[Monitor] Shipment {data['shipment_id']}: "
                f"{delay['severity']} delay ({delay['extra_minutes']} min)"
            )
            # Generate alerts
            customer_msg = generate_customer_alert_arabic(
                data.get("order_id", "N/A"), delay
            )
            driver_msg = generate_driver_alert_arabic(delay)

            # If critical, trigger reroute
            if delay["severity"] == "critical":
                remaining = data.get("remaining_stops", [])
                new_route = suggest_reroute(
                    remaining,
                    data.get("driver_lat", 30.0),
                    data.get("driver_lng", 31.2),
                )
                driver_msg = generate_driver_alert_arabic(delay, new_route)

            return {
                "delayed": True,
                "customer_alert": customer_msg,
                "driver_alert": driver_msg,
                "delay": delay,
            }

        return {"delayed": False}

    return _monitor.delay(shipment_data)


def send_notification_task(chat_id: str, message: str):
    """Queue Telegram notification through Celery."""
    celery = get_celery()

    @celery.task(name="fastdrop.send_telegram_notification")
    def _send(cid, msg):
        import httpx
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            return {"error": "No bot token"}

        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": cid, "text": msg, "parse_mode": "HTML"},
        )
        return r.json()

    return _send.delay(chat_id, message)
