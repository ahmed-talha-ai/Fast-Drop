# api/orders.py
# ═══════════════════════════════════════════════════════════
# Order CRUD + State Machine API
# 9 states with validated transitions
# ═══════════════════════════════════════════════════════════
import random
import string
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from database import get_db
from models import Order, OrderStatus, can_transition, Customer

logger = logging.getLogger("fastdrop.api.orders")
router = APIRouter(prefix="/api/orders", tags=["Orders"])


# ═══════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════
class OrderCreate(BaseModel):
    customer_id: int
    pickup_address: str
    delivery_address: str
    weight_kg: float = 1.0
    cod_amount: float = 0.0
    notes_ar: str | None = None
    scheduled_date: str | None = None


class OrderStatusUpdate(BaseModel):
    status: str


class OrderResponse(BaseModel):
    id: str
    customer_id: int
    pickup_address: str
    delivery_address: str
    weight_kg: float
    cod_amount: float
    status: str
    delivery_fee: float | None
    created_at: datetime | None
    eta: datetime | None

    class Config:
        from_attributes = True


def generate_order_id() -> str:
    """Generate order ID: ORD-2026-XXXXX"""
    year = datetime.now().year
    rand = "".join(random.choices(string.digits, k=5))
    return f"ORD-{year}-{rand}"


# ═══════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════
@router.get("/")
async def list_orders(
    status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all orders with optional status filter."""
    from sqlalchemy import func
    query = select(Order).order_by(Order.created_at.desc()).limit(limit)
    if status:
        try:
            query = query.where(Order.status == OrderStatus(status))
        except ValueError:
            pass
    result = await db.execute(query)
    orders = result.scalars().all()
    return [
        {
            "id": o.id,
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "delivery_address": o.delivery_address,
            "pickup_address": o.pickup_address,
            "weight_kg": o.weight_kg,
            "delivery_fee": o.delivery_fee,
            "created_at": str(o.created_at) if o.created_at else None,
        }
        for o in orders
    ]


@router.get("/stats")
async def order_stats(db: AsyncSession = Depends(get_db)):
    """Quick stats: count per status."""
    from sqlalchemy import func
    result = await db.execute(
        select(Order.status, func.count().label("count")).group_by(Order.status)
    )
    rows = result.all()
    stats = {row.status.value: row.count for row in rows}
    total = sum(stats.values())
    return {"total": total, "by_status": stats}


@router.post("/", response_model=OrderResponse)
async def create_order(data: OrderCreate, db: AsyncSession = Depends(get_db)):
    """Create a new delivery order with geocoding + fee calculation."""
    # Geocode addresses
    try:
        from core.geocoder import geocode_address
        pickup = await geocode_address(data.pickup_address)
        delivery = await geocode_address(data.delivery_address)
    except Exception as e:
        logger.warning(f"Geocoding failed: {e}")
        pickup = {"lat": None, "lng": None}
        delivery = {"lat": None, "lng": None}

    # Calculate fee
    fee = None
    if pickup.get("lat") and delivery.get("lat"):
        from core.zone_manager import get_delivery_fee
        fee = get_delivery_fee(
            pickup["lat"], pickup["lng"],
            delivery["lat"], delivery["lng"],
        )

    # Detect zone
    zone_id = None
    if delivery.get("lat"):
        from core.zone_manager import find_zone_by_coords
        zone = find_zone_by_coords(delivery["lat"], delivery["lng"])
        zone_id = zone["id"] if zone else None

    order = Order(
        id=generate_order_id(),
        customer_id=data.customer_id,
        pickup_address=data.pickup_address,
        pickup_lat=pickup.get("lat"),
        pickup_lng=pickup.get("lng"),
        delivery_address=data.delivery_address,
        delivery_lat=delivery.get("lat"),
        delivery_lng=delivery.get("lng"),
        delivery_zone_id=zone_id,
        weight_kg=data.weight_kg,
        cod_amount=data.cod_amount,
        notes_ar=data.notes_ar,
        delivery_fee=fee,
        status=OrderStatus.CREATED,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    logger.info(f"[Order] Created: {order.id} → zone={zone_id} fee={fee}")
    return order


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Get order details by ID."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, f"لم نجد أوردر #{order_id}")
    return order


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: str,
    data: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Transition order status using state machine rules.
    Only valid transitions are allowed.
    """
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, f"لم نجد أوردر #{order_id}")

    try:
        new_status = OrderStatus(data.status)
    except ValueError:
        raise HTTPException(
            400,
            f"حالة غير صحيحة: {data.status}. "
            f"الحالات المتاحة: {[s.value for s in OrderStatus]}"
        )

    current = order.status
    if not can_transition(current, new_status):
        raise HTTPException(
            400,
            f"لا يمكن التحويل من '{current.value}' إلى '{new_status.value}'. "
            f"الانتقالات المسموحة: {[s.value for s in __import__('models').ORDER_TRANSITIONS.get(current, [])]}"
        )

    order.status = new_status
    order.updated_at = datetime.now()
    await db.commit()

    # Side effects
    if new_status == OrderStatus.OUT_FOR_DELIVERY:
        # Notify customer via Telegram
        try:
            customer = await db.execute(
                select(Customer).where(Customer.id == order.customer_id)
            )
            cust = customer.scalar_one_or_none()
            if cust and cust.telegram_chat_id:
                from ai.event_handler import send_notification_task
                from core.arabic_normalizer import arabic_status
                send_notification_task(
                    cust.telegram_chat_id,
                    f"🚚 الأوردر #{order.id}\n{arabic_status(new_status.value)}"
                )
        except Exception:
            pass

    return {
        "order_id": order_id,
        "previous_status": current.value,
        "new_status": new_status.value,
        "message_ar": f"الأوردر #{order_id} اتحدث لـ: {__import__('core.arabic_normalizer', fromlist=['arabic_status']).arabic_status(new_status.value)}",
    }


@router.get("/customer/{customer_id}")
async def list_customer_orders(
    customer_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List orders for a specific customer."""
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    orders = result.scalars().all()
    return {"customer_id": customer_id, "orders": [
        {
            "id": o.id,
            "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
            "delivery_address": o.delivery_address,
            "delivery_fee": o.delivery_fee,
            "created_at": str(o.created_at) if o.created_at else None,
        }
        for o in orders
    ]}
