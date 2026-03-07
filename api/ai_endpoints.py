# api/ai_endpoints.py
# ═══════════════════════════════════════════════════════════
# AI Microservice Endpoints — for .NET Core integration
# All AI/ML logic exposed as JSON-in → JSON-out REST APIs
# ═══════════════════════════════════════════════════════════
import logging
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger("fastdrop.api.ai")
router = APIRouter(prefix="/api/ai", tags=["AI Engine"])


# ═══════════════════════════════════════════════
# Request / Response Schemas
# ═══════════════════════════════════════════════

class OrderPoint(BaseModel):
    """Single order with location data."""
    id: str
    lat: float
    lng: float
    weight_kg: float = 1.0


class DriverInfo(BaseModel):
    """Driver info for dispatch assignment."""
    id: int
    name: str
    lat: float | None = None
    lng: float | None = None
    max_weight_kg: float = 50.0
    performance_score: float = 0.8
    vehicle_type: str = "motorcycle"


# ── 1. Cluster Orders ────────────────────────────
class ClusterRequest(BaseModel):
    orders: list[OrderPoint]
    eps_km: float = Field(default=3.0, description="DBSCAN radius in km")
    min_samples: int = Field(default=3, description="Min orders per cluster")


class ClusterResponse(BaseModel):
    cluster_count: int
    clusters: dict[str, list[dict]]
    total_orders: int


# ── 2. Optimize Route ────────────────────────────
class RouteRequest(BaseModel):
    orders: list[OrderPoint]
    depot_lat: float = Field(default=30.0444, description="Starting point lat")
    depot_lng: float = Field(default=31.2357, description="Starting point lng")
    num_vehicles: int = 1
    max_weight_kg: float = 50.0


class RouteStop(BaseModel):
    sequence: int
    order_id: str
    lat: float
    lng: float
    vehicle: int = 0


# ── 3. Dispatch (Full Pipeline) ────────────────
class DispatchRequest(BaseModel):
    orders: list[OrderPoint]
    drivers: list[DriverInfo]
    depot_lat: float = 30.0444
    depot_lng: float = 31.2357
    eps_km: float = 3.0


# ── 4. Detect Delay ────────────────────────────
class DelayRequest(BaseModel):
    current_time: str = Field(description="ISO 8601 datetime string")
    estimated_arrival: str = Field(description="ISO 8601 datetime string")
    actual_progress_pct: float = Field(description="0.0–1.0 actual progress")
    expected_progress_pct: float = Field(description="0.0–1.0 expected progress")


# ── 5. Reroute ────────────────────────────────
class RerouteRequest(BaseModel):
    remaining_stops: list[dict]
    current_lat: float
    current_lng: float


# ── 6. Alert ──────────────────────────────────
class AlertRequest(BaseModel):
    order_id: str
    delay_info: dict = Field(description="Output from /detect-delay")
    alert_type: str = Field(default="customer", description="'customer' or 'driver'")
    new_route: list[dict] | None = None


# ═══════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════

@router.post("/cluster-orders", response_model=ClusterResponse)
async def cluster_orders(data: ClusterRequest):
    """
    Cluster delivery orders geographically using DBSCAN.

    Groups nearby orders together for efficient batch delivery.
    Used by the .NET Dispatch Service before route optimization.

    Example: 50 orders across Cairo → 8 geographic clusters.
    """
    from ai.clustering import cluster_orders_dbscan

    orders = [o.model_dump() for o in data.orders]
    clusters = cluster_orders_dbscan(
        orders,
        eps_km=data.eps_km,
        min_samples=data.min_samples,
    )

    return ClusterResponse(
        cluster_count=len(clusters),
        clusters={str(k): v for k, v in clusters.items()},
        total_orders=len(orders),
    )


@router.post("/optimize-route", response_model=list[RouteStop])
async def optimize_route(data: RouteRequest):
    """
    Optimize delivery route using Google OR-Tools VRP solver.

    Takes a list of orders and returns the optimal stop sequence
    that minimizes total travel distance.

    Input: Unordered list of orders + depot (warehouse) location.
    Output: Ordered list of stops with sequence numbers.
    """
    from ai.clustering import optimize_route_vrp

    orders = [o.model_dump() for o in data.orders]
    route = optimize_route_vrp(
        orders,
        depot_lat=data.depot_lat,
        depot_lng=data.depot_lng,
        num_vehicles=data.num_vehicles,
        max_weight_kg=data.max_weight_kg,
    )

    return route


@router.post("/dispatch")
async def dispatch_orders(data: DispatchRequest):
    """
    Full AI dispatch pipeline: Cluster → Assign Drivers → Optimize Routes.

    This is the main entry point for the .NET Dispatch Service.
    Sends unassigned orders + available drivers → returns shipment plans.

    Pipeline:
    1. DBSCAN clusters orders geographically
    2. Assigns best driver per cluster (round-robin by score)
    3. OR-Tools VRP optimizes route within each cluster
    """
    from ai.clustering import plan_delivery_routes

    orders = [o.model_dump() for o in data.orders]
    drivers = [d.model_dump() for d in data.drivers]

    shipments = plan_delivery_routes(
        orders=orders,
        drivers=drivers,
        depot_lat=data.depot_lat,
        depot_lng=data.depot_lng,
        eps_km=data.eps_km,
    )

    return {
        "shipment_count": len(shipments),
        "shipments": shipments,
        "total_orders": len(orders),
        "drivers_used": len(set(
            s["driver"]["id"] for s in shipments
            if s.get("driver")
        )),
    }


@router.post("/detect-delay")
async def check_delay(data: DelayRequest):
    """
    Detect if a shipment is delayed based on progress vs expectations.

    Returns delay severity (minor/major/critical) and estimated
    extra minutes. Used by .NET to trigger alerts and re-routing.
    """
    from ai.event_handler import detect_delay

    current = datetime.fromisoformat(data.current_time)
    estimated = datetime.fromisoformat(data.estimated_arrival)

    result = detect_delay(
        current_time=current,
        estimated_arrival=estimated,
        actual_progress_pct=data.actual_progress_pct,
        expected_progress_pct=data.expected_progress_pct,
    )

    return result


@router.post("/reroute")
async def reroute_driver(data: RerouteRequest):
    """
    Re-optimize remaining stops from current driver GPS position.

    Called when a delay is detected or a stop is skipped.
    Uses OR-Tools VRP to recalculate the optimal path.
    """
    from ai.event_handler import suggest_reroute

    new_route = suggest_reroute(
        remaining_stops=data.remaining_stops,
        current_lat=data.current_lat,
        current_lng=data.current_lng,
    )

    return {
        "rerouted": True,
        "stop_count": len(new_route),
        "route": new_route,
    }


@router.post("/alert")
async def generate_alert(data: AlertRequest):
    """
    Generate Arabic notification text for customer or driver.

    Types:
    - customer: Egyptian Arabic delay alert for the customer
    - driver: Egyptian Arabic alert with optional new route info
    """
    from ai.event_handler import (
        generate_customer_alert_arabic,
        generate_driver_alert_arabic,
    )

    if data.alert_type == "driver":
        message = generate_driver_alert_arabic(
            delay_info=data.delay_info,
            new_route=data.new_route,
        )
    else:
        message = generate_customer_alert_arabic(
            order_id=data.order_id,
            delay_info=data.delay_info,
        )

    return {
        "alert_type": data.alert_type,
        "order_id": data.order_id,
        "message_ar": message,
    }


# ═══════════════════════════════════════════════
# NEW: 8 Advanced AI Endpoints (Smart Features)
# ═══════════════════════════════════════════════

# ── 7. ETA Prediction ──────────────────────────
class ETARequest(BaseModel):
    pickup_lat: float
    pickup_lng: float
    delivery_lat: float
    delivery_lng: float
    current_time: str | None = Field(default=None, description="ISO 8601, defaults to now")
    zone_name: str | None = None


@router.post("/predict-eta")
async def predict_eta_endpoint(data: ETARequest):
    """
    Predict delivery ETA based on distance, Cairo traffic patterns,
    time of day, zone congestion, and day of week.

    Example: Maadi → 5th Settlement at 5pm = ~55 min (evening rush).
    """
    from ai.smart_features import predict_eta
    return predict_eta(
        pickup_lat=data.pickup_lat, pickup_lng=data.pickup_lng,
        delivery_lat=data.delivery_lat, delivery_lng=data.delivery_lng,
        current_time=data.current_time, zone_name=data.zone_name,
    )


# ── 8. Demand Forecasting ─────────────────────
class DemandRequest(BaseModel):
    zone_name: str | None = Field(default=None, description="Zone name, or null for all")
    target_date: str | None = Field(default=None, description="ISO 8601 date")
    hours_ahead: int = Field(default=6, ge=1, le=24)


@router.post("/forecast-demand")
async def forecast_demand_endpoint(data: DemandRequest):
    """
    Forecast delivery demand per zone for the next N hours.

    Used for proactive driver positioning and capacity planning.
    Returns hourly predictions, peak hours, and recommended driver count.
    """
    from ai.smart_features import forecast_demand
    return forecast_demand(
        zone_name=data.zone_name,
        target_date=data.target_date,
        hours_ahead=data.hours_ahead,
    )


# ── 9. Fraud / Anomaly Detection ──────────────
class AnomalyRequest(BaseModel):
    customer_id: int
    pickup_lat: float
    pickup_lng: float
    delivery_lat: float
    delivery_lng: float
    weight_kg: float
    cod_amount: float = 0
    order_time: str | None = None
    recent_order_count: int = 0


@router.post("/check-anomaly")
async def check_anomaly_endpoint(data: AnomalyRequest):
    """
    Check an order for fraud and anomalies.

    Detects: same address, excessive weight, high COD, off-hours,
    rapid ordering, unreachable areas. Returns risk score (0-100).
    """
    from ai.smart_features import check_anomaly
    return check_anomaly(
        customer_id=data.customer_id,
        pickup_lat=data.pickup_lat, pickup_lng=data.pickup_lng,
        delivery_lat=data.delivery_lat, delivery_lng=data.delivery_lng,
        weight_kg=data.weight_kg, cod_amount=data.cod_amount,
        order_time=data.order_time,
        recent_order_count=data.recent_order_count,
    )


# ── 10. Smart Driver Matching ─────────────────
class MatchDriverInfo(BaseModel):
    id: int
    name: str
    lat: float = 30.044
    lng: float = 31.235
    max_weight_kg: float = 20.0
    performance_score: float = 0.8
    vehicle_type: str = "motorcycle"
    current_orders: int = 0


class MatchRequest(BaseModel):
    order: OrderPoint
    drivers: list[MatchDriverInfo]


@router.post("/match-driver")
async def match_driver_endpoint(data: MatchRequest):
    """
    Find the best driver for an order using ML-based multi-factor scoring.

    Factors: proximity (35%), performance (25%), capacity (20%), workload (20%).
    Returns ranked list of all drivers with detailed score breakdown.
    """
    from ai.smart_features import match_driver
    return match_driver(
        order=data.order.model_dump(),
        drivers=[d.model_dump() for d in data.drivers],
    )


# ── 11. Dynamic Pricing ───────────────────────
class PricingRequest(BaseModel):
    pickup_lat: float
    pickup_lng: float
    delivery_lat: float
    delivery_lng: float
    weight_kg: float = 1.0
    cod_amount: float = 0.0
    zone_name: str | None = None
    current_time: str | None = None
    demand_level: str = Field(default="normal", description="low|normal|high|surge")


@router.post("/dynamic-pricing")
async def dynamic_pricing_endpoint(data: PricingRequest):
    """
    Calculate delivery fee with dynamic pricing.

    Factors: base zone fee + distance + weight + time surcharge +
    demand multiplier + COD fee + day surcharge.
    """
    from ai.smart_features import calculate_dynamic_price
    return calculate_dynamic_price(
        pickup_lat=data.pickup_lat, pickup_lng=data.pickup_lng,
        delivery_lat=data.delivery_lat, delivery_lng=data.delivery_lng,
        weight_kg=data.weight_kg, cod_amount=data.cod_amount,
        zone_name=data.zone_name, current_time=data.current_time,
        demand_level=data.demand_level,
    )


# ── 12. Sentiment Analysis ────────────────────
class SentimentRequest(BaseModel):
    message: str = Field(description="Customer message (Arabic or English)")


@router.post("/analyze-sentiment")
async def analyze_sentiment_endpoint(data: SentimentRequest):
    """
    Analyze customer message sentiment for support prioritization.

    Detects positive, negative, and urgent keywords in Arabic & English.
    Returns sentiment score (-1 to 1), priority level, and recommended action.
    """
    from ai.smart_features import analyze_sentiment
    return analyze_sentiment(data.message)


# ── 13. Driver Behavior Analysis ──────────────
class BehaviorRequest(BaseModel):
    driver_id: int
    deliveries_completed: int = 0
    deliveries_failed: int = 0
    avg_delivery_time_min: float = 30
    cancellation_count: int = 0
    customer_complaints: int = 0
    avg_rating: float = 4.5
    days_active: int = 30
    total_distance_km: float = 500


@router.post("/driver-behavior")
async def driver_behavior_endpoint(data: BehaviorRequest):
    """
    Analyze driver behavior patterns and generate insights.

    Detects patterns: fast/slow deliverer, reliable/unreliable,
    high cancellation, complaint rate, high volume, top rated.
    Returns overall assessment with Arabic recommendations.
    """
    from ai.smart_features import analyze_driver_behavior
    return analyze_driver_behavior(**data.model_dump())


# ── 14. Zone Heatmap ──────────────────────────
class HeatmapRequest(BaseModel):
    current_time: str | None = Field(default=None, description="ISO 8601, defaults to now")
    include_forecast: bool = True


@router.post("/zone-heatmap")
async def zone_heatmap_endpoint(data: HeatmapRequest):
    """
    Generate zone-based order density heatmap for all service areas.

    Returns color-coded zones by activity level (hot/warm/mild/cool),
    with next-hour trend forecast and driver recommendations.
    """
    from ai.smart_features import generate_zone_heatmap
    return generate_zone_heatmap(
        current_time=data.current_time,
        include_forecast=data.include_forecast,
    )

