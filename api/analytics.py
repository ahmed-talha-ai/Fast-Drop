# api/analytics.py
# ═══════════════════════════════════════════════════════════
# Analytics API — Natural language → SQL → Insights
# ═══════════════════════════════════════════════════════════
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db, engine

logger = logging.getLogger("fastdrop.api.analytics")
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


class AnalyticsQuery(BaseModel):
    question: str
    language: str = "ar"


@router.post("/query")
async def analytics_query(
    data: AnalyticsQuery,
    db: AsyncSession = Depends(get_db),
):
    """
    Ask business questions in Arabic or English → get SQL + insight.

    Examples (Arabic):
    - "كام أوردر اتعمل النهارده؟"
    - "إيه المنطقة اللي فيها أكتر تأخير؟"
    - "مين أحسن سواق الأسبوع ده؟"

    Examples (English):
    - "How many orders were delivered this week?"
    - "Which zone has the most failed deliveries?"
    """
    from ai.analytics_agent import handle_analytics_query

    result = await handle_analytics_query(
        question=data.question,
        db_session=db,
        engine=engine,
        response_lang=data.language,
    )
    return result


@router.get("/dashboard")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Quick dashboard stats — no LLM, pure SQL."""
    from sqlalchemy import select, func
    from models import Order, OrderStatus, Driver, DriverStatus

    # Total orders today
    orders_today = await db.execute(
        select(func.count()).select_from(Order).where(
            func.date(Order.created_at) == func.current_date()
        )
    )

    # Active drivers
    active_drivers = await db.execute(
        select(func.count()).select_from(Driver).where(
            Driver.status == DriverStatus.AVAILABLE
        )
    )

    # Delivered today
    delivered_today = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.status == OrderStatus.DELIVERED,
            func.date(Order.updated_at) == func.current_date(),
        )
    )

    # Failed today
    failed_today = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.status == OrderStatus.FAILED,
            func.date(Order.updated_at) == func.current_date(),
        )
    )

    return {
        "date": str(__import__("datetime").date.today()),
        "orders_today": orders_today.scalar() or 0,
        "delivered_today": delivered_today.scalar() or 0,
        "failed_today": failed_today.scalar() or 0,
        "active_drivers": active_drivers.scalar() or 0,
    }


@router.get("/rate-limits")
async def rate_limit_stats():
    """Show current LLM API usage across all providers."""
    from core.rate_limiter import get_all_usage
    return {"usage": get_all_usage()}


@router.get("/cache-stats")
async def cache_stats():
    """Show RAG cache statistics."""
    from rag.rag_cache import get_cache_stats
    return get_cache_stats()


@router.get("/summary")
async def summary_stats(db: AsyncSession = Depends(get_db)):
    """Alias for /dashboard — quick summary stats."""
    return await dashboard_stats(db)


@router.get("/revenue")
async def revenue_stats(db: AsyncSession = Depends(get_db)):
    """Total revenue and average delivery fee."""
    from sqlalchemy import func, select
    from models import Order, OrderStatus

    result = await db.execute(
        select(
            func.count().label("total_delivered"),
            func.sum(Order.delivery_fee).label("total_revenue"),
            func.avg(Order.delivery_fee).label("avg_fee"),
        ).where(Order.status == OrderStatus.DELIVERED)
    )
    row = result.one()
    return {
        "total_delivered_orders": row.total_delivered or 0,
        "total_revenue_egp": round(float(row.total_revenue or 0), 2),
        "average_delivery_fee_egp": round(float(row.avg_fee or 0), 2),
    }
