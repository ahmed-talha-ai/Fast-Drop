# ai/clustering.py
# ═══════════════════════════════════════════════════════════════════
# Geographic Clustering + Route Optimization
# DBSCAN for order clustering → OR-Tools VRP for optimal routes
# Pure deterministic math — no LLM calls.
# ═══════════════════════════════════════════════════════════════════
import numpy as np
import logging
from collections import defaultdict
from math import radians, sin, cos, sqrt, atan2

logger = logging.getLogger("fastdrop.clustering")


def haversine_m(lat1, lng1, lat2, lng2):
    """Haversine distance in meters."""
    R = 6_371_000
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


# ═══════════════════════════════════════════════
# DBSCAN Geographic Clustering
# ═══════════════════════════════════════════════
def cluster_orders_dbscan(
    orders: list[dict],
    eps_km: float = 3.0,
    min_samples: int = 3,
) -> dict[int, list[dict]]:
    """
    Cluster delivery orders geographically using DBSCAN.
    
    Args:
        orders: [{"id": ..., "lat": ..., "lng": ..., "weight_kg": ...}, ...]
        eps_km: Maximum distance between two points in same cluster (km)
        min_samples: Minimum orders to form a cluster
        
    Returns: {cluster_id: [orders], -1: [noise_orders]}
    """
    from sklearn.cluster import DBSCAN

    if len(orders) < min_samples:
        return {0: orders}

    coords = np.array([[o["lat"], o["lng"]] for o in orders])
    coords_rad = np.radians(coords)

    # DBSCAN with haversine metric (expects radians, returns km)
    clustering = DBSCAN(
        eps=eps_km / 6371.0,      # Convert km to radians
        min_samples=min_samples,
        metric="haversine",
    )
    labels = clustering.fit_predict(coords_rad)

    clusters = defaultdict(list)
    for order, label in zip(orders, labels):
        clusters[int(label)].append(order)

    logger.info(
        f"[DBSCAN] {len(orders)} orders → "
        f"{len(clusters)} clusters (eps={eps_km}km)"
    )
    return dict(clusters)


# ═══════════════════════════════════════════════
# OR-Tools VRP Solver
# ═══════════════════════════════════════════════
def build_distance_matrix(points: list[tuple]) -> list[list[int]]:
    """Build distance matrix (meters) from lat/lng pairs."""
    n = len(points)
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = int(haversine_m(points[i][0], points[i][1],
                                points[j][0], points[j][1]))
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def optimize_route_vrp(
    orders: list[dict],
    depot_lat: float = 30.0444,
    depot_lng: float = 31.2357,
    num_vehicles: int = 1,
    max_weight_kg: float = 50.0,
) -> list[dict]:
    """
    Solve Vehicle Routing Problem using Google OR-Tools.
    
    Args:
        orders: Clustered order list with lat/lng/weight_kg
        depot_lat/lng: Warehouse/starting point coordinates
        num_vehicles: Number of drivers available for this cluster
        max_weight_kg: Max capacity per vehicle
        
    Returns: Ordered list of route stops with sequence numbers
    """
    from ortools.constraint_solver import routing_enums_pb2, pywrapcp

    if not orders:
        return []

    # Points: depot (index 0) + order locations
    points = [(depot_lat, depot_lng)] + [(o["lat"], o["lng"]) for o in orders]
    demands = [0] + [int(o.get("weight_kg", 1) * 10) for o in orders]  # Scaled
    matrix = build_distance_matrix(points)

    # Create routing model
    manager = pywrapcp.RoutingIndexManager(len(points), num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Distance callback
    def distance_callback(from_idx, to_idx):
        from_node = manager.IndexToNode(from_idx)
        to_node = manager.IndexToNode(to_idx)
        return matrix[from_node][to_node]

    transit_id = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_id)

    # Capacity constraint
    def demand_callback(idx):
        return demands[manager.IndexToNode(idx)]

    demand_id = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_id, 0, [int(max_weight_kg * 10)] * num_vehicles,
        True, "Capacity",
    )

    # Search parameters
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.FromSeconds(5)

    # Solve
    solution = routing.SolveWithParameters(search_params)
    if not solution:
        logger.warning("[VRP] No solution found — returning unoptimized order")
        return [
            {"sequence": i + 1, **o} for i, o in enumerate(orders)
        ]

    # Extract route
    route_stops = []
    for vehicle in range(num_vehicles):
        idx = routing.Start(vehicle)
        seq = 1
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node > 0:  # Skip depot
                order = orders[node - 1]
                route_stops.append({
                    "sequence": seq,
                    "order_id": order["id"],
                    "lat": order["lat"],
                    "lng": order["lng"],
                    "vehicle": vehicle,
                })
                seq += 1
            idx = solution.Value(routing.NextVar(idx))

    total_dist = solution.ObjectiveValue()
    logger.info(f"[VRP] Route optimized: {len(route_stops)} stops, {total_dist}m total")
    return route_stops


# ═══════════════════════════════════════════════
# Full Pipeline: Cluster → Optimize
# ═══════════════════════════════════════════════
def plan_delivery_routes(
    orders: list[dict],
    drivers: list[dict],
    depot_lat: float = 30.0444,
    depot_lng: float = 31.2357,
    eps_km: float = 3.0,
) -> list[dict]:
    """
    Full pipeline: Cluster orders → Assign drivers → Optimize routes.
    
    Returns: List of shipment plans with optimized route stops.
    """
    if not orders:
        return []

    # Step 1: Cluster
    clusters = cluster_orders_dbscan(orders, eps_km=eps_km)

    # Step 2: Optimize each cluster
    shipments = []
    driver_idx = 0

    for cluster_id, cluster_orders in clusters.items():
        if cluster_id == -1:
            # Noise: assign individually
            for order in cluster_orders:
                shipments.append({
                    "cluster_id": -1,
                    "driver": drivers[driver_idx % len(drivers)] if drivers else None,
                    "route": [{"sequence": 1, **order}],
                    "order_count": 1,
                })
                driver_idx += 1
            continue

        # Assign driver for this cluster
        driver = drivers[driver_idx % len(drivers)] if drivers else None
        max_weight = driver.get("max_weight_kg", 50.0) if driver else 50.0

        route = optimize_route_vrp(
            cluster_orders,
            depot_lat=depot_lat,
            depot_lng=depot_lng,
            max_weight_kg=max_weight,
        )

        shipments.append({
            "cluster_id": cluster_id,
            "driver": driver,
            "route": route,
            "order_count": len(cluster_orders),
        })
        driver_idx += 1

    return shipments
