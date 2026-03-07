# api/drivers.py
# ═══════════════════════════════════════════════════════════
# Driver Management + GPS Location API
# ═══════════════════════════════════════════════════════════
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import Driver, DriverStatus, LocationPing, VehicleType

logger = logging.getLogger("fastdrop.api.drivers")
router = APIRouter(prefix="/api/drivers", tags=["Drivers"])


# ═══════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════
class DriverCreate(BaseModel):
    name: str
    phone: str
    vehicle_type: str = "motorcycle"
    max_weight_kg: float = 20.0
    zone_id: int | None = None
    telegram_chat_id: str | None = None


class LocationUpdate(BaseModel):
    lat: float
    lng: float
    accuracy_meters: float = 20.0
    shipment_id: str | None = None


class NearestDriverRequest(BaseModel):
    lat: float
    lng: float
    max_distance_km: float = 10.0


# ═══════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════
@router.get("/")
async def list_drivers(
    status: str | None = None,
    zone_id: int | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all drivers with optional filters (status, zone_id)."""
    query = select(Driver)
    if status:
        try:
            query = query.where(Driver.status == DriverStatus(status))
        except ValueError:
            pass
    if zone_id:
        query = query.where(Driver.zone_id == zone_id)
    query = query.limit(limit)
    result = await db.execute(query)
    drivers = result.scalars().all()
    return {
        "total": len(drivers),
        "drivers": [
            {
                "id": d.id,
                "name": d.name,
                "phone": d.phone,
                "vehicle_type": d.vehicle_type.value,
                "status": d.status.value,
                "zone_id": d.zone_id,
                "performance_score": d.performance_score,
            }
            for d in drivers
        ],
    }


@router.get("/available")
async def list_available_drivers(db: AsyncSession = Depends(get_db)):
    """List all currently available drivers."""
    result = await db.execute(
        select(Driver).where(Driver.status == DriverStatus.AVAILABLE)
    )
    drivers = result.scalars().all()
    return {
        "available_count": len(drivers),
        "drivers": [
            {"id": d.id, "name": d.name, "vehicle_type": d.vehicle_type.value, "zone_id": d.zone_id}
            for d in drivers
        ],
    }

@router.post("/")
async def create_driver(data: DriverCreate, db: AsyncSession = Depends(get_db)):
    """Register a new driver."""
    try:
        vtype = VehicleType(data.vehicle_type)
    except ValueError:
        vtype = VehicleType.MOTORCYCLE

    driver = Driver(
        name=data.name,
        phone=data.phone,
        vehicle_type=vtype,
        max_weight_kg=data.max_weight_kg,
        zone_id=data.zone_id,
        telegram_chat_id=data.telegram_chat_id,
    )
    db.add(driver)
    await db.commit()
    await db.refresh(driver)

    return {
        "id": driver.id,
        "name": driver.name,
        "phone": driver.phone,
        "vehicle_type": driver.vehicle_type.value,
        "status": driver.status.value,
    }


@router.get("/{driver_id}")
async def get_driver(driver_id: int, db: AsyncSession = Depends(get_db)):
    """Get driver profile with performance data."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, f"السواق #{driver_id} مش موجود")

    from ai.driver_scoring import get_tier, get_tier_arabic

    tier = get_tier(driver.performance_score)
    return {
        "id": driver.id,
        "name": driver.name,
        "phone": driver.phone,
        "vehicle_type": driver.vehicle_type.value,
        "status": driver.status.value,
        "performance_score": driver.performance_score,
        "tier": tier,
        "tier_ar": get_tier_arabic(tier),
        "zone_id": driver.zone_id,
    }


@router.patch("/{driver_id}/status")
async def update_driver_status(
    driver_id: int, status: str,
    db: AsyncSession = Depends(get_db),
):
    """Update driver availability status."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, f"السواق #{driver_id} مش موجود")

    try:
        new_status = DriverStatus(status)
    except ValueError:
        raise HTTPException(400, f"حالة مش صحيحة: {status}")

    driver.status = new_status
    await db.commit()

    return {
        "driver_id": driver_id,
        "status": new_status.value,
        "message_ar": f"حالة السواق اتحدثت: {new_status.value}",
    }


# ═══════════════════════════════════════════════
# GPS Location Update
# ═══════════════════════════════════════════════
@router.post("/{driver_id}/location")
async def update_location(
    driver_id: int,
    data: LocationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive GPS ping from driver's device.
    Stores in PostgreSQL for audit + Redis GEO for real-time queries.
    """
    # Store in PostgreSQL
    ping = LocationPing(
        driver_id=driver_id,
        lat=data.lat,
        lng=data.lng,
        accuracy_meters=data.accuracy_meters,
        shipment_id=data.shipment_id,
    )
    db.add(ping)
    await db.commit()

    # Store in Redis GEO for real-time nearest-driver queries
    try:
        import redis
        import os
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        r.geoadd("driver_locations", (data.lng, data.lat, f"driver:{driver_id}"))
        r.setex(f"driver_loc:{driver_id}", 300, f"{data.lat},{data.lng}")
    except Exception as e:
        logger.warning(f"Redis GEO update failed: {e}")

    return {"status": "ok", "driver_id": driver_id}


# ═══════════════════════════════════════════════
# Nearest Driver Lookup
# ═══════════════════════════════════════════════
@router.post("/nearest")
async def find_nearest_drivers(
    data: NearestDriverRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find nearest available drivers to a coordinate."""
    try:
        import redis
        import os
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        results = r.georadius(
            "driver_locations",
            data.lng, data.lat,
            data.max_distance_km, unit="km",
            withdist=True, withcoord=True,
            sort="ASC", count=10,
        )

        drivers = []
        for member, dist, (lng, lat) in results:
            driver_id = int(member.decode().split(":")[1])
            result = await db.execute(
                select(Driver).where(
                    Driver.id == driver_id,
                    Driver.status == DriverStatus.AVAILABLE,
                )
            )
            driver = result.scalar_one_or_none()
            if driver:
                drivers.append({
                    "id": driver.id,
                    "name": driver.name,
                    "distance_km": round(dist, 2),
                    "lat": float(lat),
                    "lng": float(lng),
                    "vehicle_type": driver.vehicle_type.value,
                    "score": driver.performance_score,
                })
        return {"nearby_drivers": drivers}

    except Exception as e:
        logger.warning(f"Redis GEO search failed: {e}")
        # Fallback: return all available drivers
        result = await db.execute(
            select(Driver).where(Driver.status == DriverStatus.AVAILABLE).limit(10)
        )
        drivers = result.scalars().all()
        return {
            "nearby_drivers": [
                {"id": d.id, "name": d.name, "score": d.performance_score}
                for d in drivers
            ],
            "note": "Fallback: Redis unavailable, showing all available drivers",
        }


@router.get("/{driver_id}/score")
async def get_driver_score(driver_id: int, db: AsyncSession = Depends(get_db)):
    """Get driver's current performance score and update it."""
    from ai.driver_scoring import update_driver_score
    return await update_driver_score(driver_id, db)


@router.get("/leaderboard/top")
async def driver_leaderboard(db: AsyncSession = Depends(get_db)):
    """Top 10 drivers by performance score."""
    from ai.driver_scoring import get_top_drivers
    return {"leaderboard": await get_top_drivers(db)}
