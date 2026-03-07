# seed_data.py — Seed the FastDrop database with test data
# Run: python seed_data.py
import asyncio
import os
import sys

# Fix Windows console encoding for Arabic/emoji
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, AsyncSessionLocal
from models import (
    Base, Customer, Driver, Zone,
    VehicleType, DriverStatus,
)
from core.zone_manager import CAIRO_ZONES


async def seed():
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created/verified")

    async with AsyncSessionLocal() as db:
        # ── 1. Seed Zones ──────────────────────────
        from sqlalchemy import select, func
        zone_count = (await db.execute(select(func.count()).select_from(Zone))).scalar()
        if zone_count == 0:
            for z in CAIRO_ZONES:
                zone = Zone(
                    id=z["id"],
                    name_ar=z["name_ar"],
                    name_en=z["name_en"],
                    center_lat=z["center_lat"],
                    center_lng=z["center_lng"],
                    base_delivery_fee=z["base_fee"],
                    max_orders_per_day=z.get("max_daily", 200),
                    working_hours_start=z["hours"][0],
                    working_hours_end=z["hours"][1],
                )
                db.add(zone)
            await db.commit()
            print(f"✅ Seeded {len(CAIRO_ZONES)} zones")
        else:
            print(f"⏭️  Zones already exist ({zone_count} rows)")

        # ── 2. Seed Customers ────────────────────────
        cust_count = (await db.execute(select(func.count()).select_from(Customer))).scalar()
        if cust_count == 0:
            customers = [
                Customer(name="محمد أحمد", phone="01012345678", email="mohamed@test.com", preferred_language="ar"),
                Customer(name="فاطمة حسن", phone="01098765432", email="fatma@test.com", preferred_language="ar"),
                Customer(name="أحمد محمود", phone="01112223333", email="ahmed.m@test.com", preferred_language="ar"),
                Customer(name="سارة عبدالله", phone="01234567890", email="sara@test.com", preferred_language="ar"),
                Customer(name="John Smith", phone="01055566677", email="john@test.com", preferred_language="en"),
            ]
            db.add_all(customers)
            await db.commit()
            print(f"✅ Seeded {len(customers)} customers")
        else:
            print(f"⏭️  Customers already exist ({cust_count} rows)")

        # ── 3. Seed Drivers ──────────────────────────
        driver_count = (await db.execute(select(func.count()).select_from(Driver))).scalar()
        if driver_count == 0:
            drivers = [
                Driver(
                    name="حسن إبراهيم", phone="01199887766",
                    vehicle_type=VehicleType.MOTORCYCLE, max_weight_kg=15.0,
                    status=DriverStatus.AVAILABLE, zone_id=1,
                    performance_score=0.92,
                ),
                Driver(
                    name="علي محمد", phone="01188776655",
                    vehicle_type=VehicleType.MOTORCYCLE, max_weight_kg=20.0,
                    status=DriverStatus.AVAILABLE, zone_id=2,
                    performance_score=0.88,
                ),
                Driver(
                    name="كريم سعيد", phone="01177665544",
                    vehicle_type=VehicleType.CAR, max_weight_kg=50.0,
                    status=DriverStatus.AVAILABLE, zone_id=4,
                    performance_score=0.95,
                ),
                Driver(
                    name="عمر خالد", phone="01166554433",
                    vehicle_type=VehicleType.VAN, max_weight_kg=100.0,
                    status=DriverStatus.EN_ROUTE, zone_id=8,
                    performance_score=0.85,
                ),
                Driver(
                    name="ياسر أحمد", phone="01155443322",
                    vehicle_type=VehicleType.MOTORCYCLE, max_weight_kg=15.0,
                    status=DriverStatus.OFFLINE, zone_id=11,
                    performance_score=0.78,
                ),
            ]
            db.add_all(drivers)
            await db.commit()
            print(f"✅ Seeded {len(drivers)} drivers")
        else:
            print(f"⏭️  Drivers already exist ({driver_count} rows)")

    print("\n🎉 Database seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
