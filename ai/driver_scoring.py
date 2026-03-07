# ai/driver_scoring.py
# ═══════════════════════════════════════════════════════════════════
# Driver Performance Scoring — Weighted KPI Formula
# Updates daily based on delivery outcomes, punctuality, and ratings.
# ═══════════════════════════════════════════════════════════════════
import logging
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("fastdrop.scoring")

# ═══════════════════════════════════════════════
# Scoring Weights
# ═══════════════════════════════════════════════
WEIGHTS = {
    "success_rate": 0.35,     # Delivery success rate
    "on_time_rate": 0.25,     # On-time delivery rate
    "customer_rating": 0.20,  # Average customer rating (1-5 → 0-1)
    "complaints": 0.10,       # Inverse complaint rate
    "volume": 0.10,           # Daily delivery volume bonus
}

# Thresholds for performance tiers
TIER_THRESHOLDS = {
    "excellent": 0.90,   # 90%+ → priority assignment
    "good": 0.75,        # 75-89% → normal
    "average": 0.60,     # 60-74% → watchlist
    "poor": 0.0,         # <60% → review needed
}


def calculate_score(
    deliveries_completed: int,
    deliveries_failed: int,
    on_time_rate: float,
    avg_rating: float,
    complaints: int,
    target_daily_volume: int = 20,
) -> float:
    """
    Calculate weighted performance score (0.0 - 1.0).
    
    Formula:
        Score = 0.35 * success_rate 
              + 0.25 * on_time_rate 
              + 0.20 * (rating / 5.0)
              + 0.10 * (1 - complaint_rate) 
              + 0.10 * volume_bonus
    """
    total = deliveries_completed + deliveries_failed
    if total == 0:
        return 0.5  # New driver default

    # Component scores
    success_rate = deliveries_completed / total
    rating_norm = min(avg_rating / 5.0, 1.0)
    complaint_rate = min(complaints / max(total, 1), 1.0)
    volume_bonus = min(deliveries_completed / target_daily_volume, 1.0)

    score = (
        WEIGHTS["success_rate"] * success_rate
        + WEIGHTS["on_time_rate"] * on_time_rate
        + WEIGHTS["customer_rating"] * rating_norm
        + WEIGHTS["complaints"] * (1 - complaint_rate)
        + WEIGHTS["volume"] * volume_bonus
    )

    return round(min(max(score, 0.0), 1.0), 4)


def get_tier(score: float) -> str:
    """Map score to performance tier."""
    for tier, threshold in sorted(
        TIER_THRESHOLDS.items(), key=lambda x: -x[1]
    ):
        if score >= threshold:
            return tier
    return "poor"


def get_tier_arabic(tier: str) -> str:
    """Get Egyptian Arabic label for performance tier."""
    return {
        "excellent": "⭐ ممتاز — أحسن سواق!",
        "good": "✅ كويس — شغل تمام",
        "average": "⚠️ متوسط — محتاج تحسين",
        "poor": "❌ ضعيف — محتاج مراجعة",
    }.get(tier, tier)


# ═══════════════════════════════════════════════
# Database-Backed Daily Update
# ═══════════════════════════════════════════════
async def update_driver_score(
    driver_id: int,
    db: AsyncSession,
) -> dict:
    """
    Calculate and persist today's performance score for a driver.
    Queries delivery_attempts and updates both PerformanceScore
    and Driver.performance_score.
    """
    from models import (
        DeliveryAttempt, PerformanceScore, Driver,
    )

    today = datetime.now().date()

    # Query today's delivery stats
    result = await db.execute(
        select(
            func.count().filter(DeliveryAttempt.status == "success").label("success"),
            func.count().filter(DeliveryAttempt.status == "failed").label("failed"),
            func.count().filter(DeliveryAttempt.status == "rescheduled").label("rescheduled"),
        ).where(
            DeliveryAttempt.driver_id == driver_id,
            func.date(DeliveryAttempt.attempted_at) == today,
        )
    )
    stats = result.one()
    completed = stats.success or 0
    failed = stats.failed or 0

    # Calculate score (use defaults for on_time_rate and rating for now)
    score = calculate_score(
        deliveries_completed=completed,
        deliveries_failed=failed,
        on_time_rate=0.85,      # TODO: compute from arrival timestamps
        avg_rating=4.5,          # TODO: compute from customer reviews
        complaints=0,            # TODO: query complaints table
    )

    tier = get_tier(score)

    # Persist performance score
    perf = PerformanceScore(
        driver_id=driver_id,
        date=datetime.now(),
        deliveries_completed=completed,
        deliveries_failed=failed,
        on_time_rate=0.85,
        avg_rating=4.5,
        complaints=0,
        weighted_score=score,
    )
    db.add(perf)

    # Update driver's rolling score
    result = await db.execute(
        select(Driver).where(Driver.id == driver_id)
    )
    driver = result.scalar_one_or_none()
    if driver:
        # Exponential moving average (α=0.3 for recent bias)
        alpha = 0.3
        driver.performance_score = round(
            alpha * score + (1 - alpha) * driver.performance_score, 4
        )

    await db.commit()

    logger.info(
        f"[Scoring] Driver {driver_id}: score={score:.3f} "
        f"tier={tier} ({completed}/{completed + failed} today)"
    )

    return {
        "driver_id": driver_id,
        "score": score,
        "tier": tier,
        "tier_ar": get_tier_arabic(tier),
        "delivered": completed,
        "failed": failed,
        "date": str(today),
    }


async def get_top_drivers(
    db: AsyncSession, limit: int = 10
) -> list[dict]:
    """Get top-performing drivers for priority assignment."""
    from models import Driver

    result = await db.execute(
        select(Driver)
        .where(Driver.is_active == True)
        .order_by(Driver.performance_score.desc())
        .limit(limit)
    )
    drivers = result.scalars().all()

    return [
        {
            "id": d.id,
            "name": d.name,
            "score": d.performance_score,
            "tier": get_tier(d.performance_score),
            "tier_ar": get_tier_arabic(get_tier(d.performance_score)),
        }
        for d in drivers
    ]
