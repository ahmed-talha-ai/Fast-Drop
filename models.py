# models.py — Full Database Schema for FastDrop
# ═══════════════════════════════════════════════
# All SQLAlchemy ORM models used across every module.
# Run: alembic revision --autogenerate && alembic upgrade head

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, Enum as SaEnum,
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func


# ═══════════════════════════════════════════════
# Base
# ═══════════════════════════════════════════════
class Base(DeclarativeBase):
    pass


# ═══════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════
class OrderStatus(str, enum.Enum):
    CREATED = "created"
    PROCESSING = "processing"
    ASSIGNED = "assigned"
    PICKED_UP = "picked_up"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"
    RESCHEDULED = "rescheduled"
    RETURNED = "returned"


class VehicleType(str, enum.Enum):
    MOTORCYCLE = "motorcycle"
    CAR = "car"
    VAN = "van"


class DriverStatus(str, enum.Enum):
    AVAILABLE = "available"
    EN_ROUTE = "en_route"
    OFFLINE = "offline"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DRIVER = "driver"
    CUSTOMER = "customer"


# ═══════════════════════════════════════════════
# Order State Machine — Transition Rules
# ═══════════════════════════════════════════════
ORDER_TRANSITIONS = {
    OrderStatus.CREATED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED
                          if hasattr(OrderStatus, "CANCELLED") else OrderStatus.RETURNED],
    OrderStatus.PROCESSING: [OrderStatus.ASSIGNED, OrderStatus.RETURNED],
    OrderStatus.ASSIGNED: [OrderStatus.PICKED_UP, OrderStatus.RETURNED],
    OrderStatus.PICKED_UP: [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.RETURNED],
    OrderStatus.OUT_FOR_DELIVERY: [OrderStatus.DELIVERED, OrderStatus.FAILED],
    OrderStatus.DELIVERED: [],  # Terminal state
    OrderStatus.FAILED: [OrderStatus.RESCHEDULED, OrderStatus.RETURNED],
    OrderStatus.RESCHEDULED: [OrderStatus.PROCESSING],
    OrderStatus.RETURNED: [],  # Terminal state
}


def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    """Check if a status transition is allowed."""
    return target in ORDER_TRANSITIONS.get(current, [])


# ═══════════════════════════════════════════════
# User (Auth)
# ═══════════════════════════════════════════════
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(SaEnum(UserRole), default=UserRole.CUSTOMER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════
# Customer
# ═══════════════════════════════════════════════
class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(120), nullable=True)
    telegram_chat_id = Column(String(40), unique=True, nullable=True)
    preferred_language = Column(String(5), default="ar")  # "ar" | "en"
    created_at = Column(DateTime, server_default=func.now())

    orders = relationship("Order", back_populates="customer")


# ═══════════════════════════════════════════════
# Driver
# ═══════════════════════════════════════════════
class Driver(Base):
    __tablename__ = "drivers"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), unique=True)
    vehicle_type = Column(SaEnum(VehicleType), default=VehicleType.MOTORCYCLE)
    max_weight_kg = Column(Float, default=20.0)
    status = Column(SaEnum(DriverStatus), default=DriverStatus.OFFLINE)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    performance_score = Column(Float, default=0.80)  # 0.0 – 1.0
    is_active = Column(Boolean, default=True)
    telegram_chat_id = Column(String(40), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    zone = relationship("Zone")
    shipments = relationship("Shipment", back_populates="driver")
    perf_scores = relationship("PerformanceScore", back_populates="driver")


# ═══════════════════════════════════════════════
# Zone (Cairo 25 zones)
# ═══════════════════════════════════════════════
class Zone(Base):
    __tablename__ = "zones"
    id = Column(Integer, primary_key=True)
    name_ar = Column(String(80), nullable=False)       # مدينة نصر
    name_en = Column(String(80), nullable=False)        # Nasr City
    city = Column(String(60), default="Cairo")
    center_lat = Column(Float, nullable=False)
    center_lng = Column(Float, nullable=False)
    boundary_polygon = Column(JSON, nullable=True)      # GeoJSON polygon
    base_delivery_fee = Column(Float, default=25.0)     # EGP
    max_orders_per_day = Column(Integer, default=200)
    working_hours_start = Column(String(5), default="09:00")
    working_hours_end = Column(String(5), default="22:00")
    is_active = Column(Boolean, default=True)


# ═══════════════════════════════════════════════
# Order
# ═══════════════════════════════════════════════
class Order(Base):
    __tablename__ = "orders"
    id = Column(String(20), primary_key=True)           # ORD-2026-XXXXX
    customer_id = Column(Integer, ForeignKey("customers.id"))
    pickup_address = Column(Text, nullable=False)
    pickup_lat = Column(Float, nullable=True)
    pickup_lng = Column(Float, nullable=True)
    delivery_address = Column(Text, nullable=False)     # Raw Arabic text
    delivery_lat = Column(Float, nullable=True)
    delivery_lng = Column(Float, nullable=True)
    delivery_zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    weight_kg = Column(Float, default=1.0)
    cod_amount = Column(Float, default=0.0)             # Cash On Delivery EGP
    status = Column(SaEnum(OrderStatus), default=OrderStatus.CREATED)
    is_return = Column(Boolean, default=False)           # Reverse logistics flag
    notes_ar = Column(Text, nullable=True)               # Driver notes in Arabic
    delivery_fee = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    scheduled_date = Column(DateTime, nullable=True)
    shipment_id = Column(String(20), ForeignKey("shipments.id"), nullable=True)
    eta = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="orders")
    delivery_zone = relationship("Zone")
    delivery_attempts = relationship("DeliveryAttempt", back_populates="order")


# ═══════════════════════════════════════════════
# Shipment (batch of orders per driver per route)
# ═══════════════════════════════════════════════
class Shipment(Base):
    __tablename__ = "shipments"
    id = Column(String(20), primary_key=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    status = Column(String(30), default="pending")
    planned_start = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    eta = Column(DateTime, nullable=True)
    driver_lat = Column(Float, nullable=True)
    driver_lng = Column(Float, nullable=True)
    route_sequence = Column(JSON, nullable=True)        # [order_id, ...] optimized
    total_distance_km = Column(Float, nullable=True)
    total_weight_kg = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    driver = relationship("Driver", back_populates="shipments")
    stops = relationship("RouteStop", back_populates="shipment")
    orders = relationship("Order", backref="shipment_ref")


# ═══════════════════════════════════════════════
# Route Stop
# ═══════════════════════════════════════════════
class RouteStop(Base):
    __tablename__ = "route_stops"
    id = Column(Integer, primary_key=True)
    shipment_id = Column(String(20), ForeignKey("shipments.id"))
    order_id = Column(String(20), ForeignKey("orders.id"))
    sequence_number = Column(Integer, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    address = Column(Text, nullable=True)
    estimated_arrival = Column(DateTime, nullable=True)
    actual_arrival = Column(DateTime, nullable=True)
    stop_status = Column(String(20), default="pending")  # pending | arrived | completed | skipped

    shipment = relationship("Shipment", back_populates="stops")
    order = relationship("Order")


# ═══════════════════════════════════════════════
# Location Pings (GPS audit trail)
# ═══════════════════════════════════════════════
class LocationPing(Base):
    __tablename__ = "location_pings"
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    accuracy_meters = Column(Float, default=20.0)
    shipment_id = Column(String(20), ForeignKey("shipments.id"), nullable=True)
    pinged_at = Column(DateTime, server_default=func.now())

    driver = relationship("Driver")


# ═══════════════════════════════════════════════
# Delivery Attempt (POD — Proof of Delivery)
# ═══════════════════════════════════════════════
class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    id = Column(Integer, primary_key=True)
    order_id = Column(String(20), ForeignKey("orders.id"))
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    attempt_number = Column(Integer, default=1)
    status = Column(String(20), nullable=False)         # success | failed | rescheduled
    otp_code = Column(String(6), nullable=True)          # 6-digit OTP
    otp_verified = Column(Boolean, default=False)
    photo_url = Column(String(500), nullable=True)       # POD photo path
    failure_reason = Column(Text, nullable=True)         # Arabic text
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    attempted_at = Column(DateTime, server_default=func.now())

    order = relationship("Order", back_populates="delivery_attempts")
    driver = relationship("Driver")


# ═══════════════════════════════════════════════
# Performance Score (Driver daily KPI)
# ═══════════════════════════════════════════════
class PerformanceScore(Base):
    __tablename__ = "performance_scores"
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    date = Column(DateTime, nullable=False)
    deliveries_completed = Column(Integer, default=0)
    deliveries_failed = Column(Integer, default=0)
    on_time_rate = Column(Float, default=1.0)            # 0.0 – 1.0
    avg_rating = Column(Float, default=5.0)              # 1.0 – 5.0
    complaints = Column(Integer, default=0)
    weighted_score = Column(Float, nullable=False)       # Computed score
    created_at = Column(DateTime, server_default=func.now())

    driver = relationship("Driver", back_populates="perf_scores")


# ═══════════════════════════════════════════════
# Rate Limit Counter (LLM API usage tracking)
# ═══════════════════════════════════════════════
class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"
    id = Column(Integer, primary_key=True)
    provider = Column(String(30), nullable=False)        # groq | gemini | openrouter
    model_id = Column(String(100), nullable=False)
    date = Column(String(10), nullable=False)            # YYYY-MM-DD
    request_count = Column(Integer, default=0)
    last_request_at = Column(DateTime, nullable=True)
    daily_limit = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
