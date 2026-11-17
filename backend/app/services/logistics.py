"""Distance, transport cost, perishability decay and OR-Tools routing."""
from __future__ import annotations

import math
from dataclasses import dataclass

ROAD_CIRCUITY = 1.3  # road km ≈ 1.3 x great-circle km on Indian rural roads
AVG_SPEED_KMPH = 35.0
Q10 = 2.0  # spoilage rate doubles for every +10°C


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def road_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return round(haversine_km(lat1, lon1, lat2, lon2) * ROAD_CIRCUITY, 1)


def transit_hours(km: float) -> float:
    return km / AVG_SPEED_KMPH + 1.0  # +1h loading/unloading


@dataclass(frozen=True)
class Vehicle:
    name: str
    capacity_qtl: float
    rate_per_km: float


VEHICLES = (
    Vehicle("pickup", 10, 16.0),   # e.g. Bolero pickup
    Vehicle("tempo", 30, 26.0),    # e.g. Tata 407
    Vehicle("truck", 100, 42.0),   # 10-tonne truck
)
RETURN_FACTOR = 1.6  # one-way loaded + partially-paid empty return
LOADING_FEE = 300.0


def transport_cost(qty_qtl: float, km: float) -> tuple[float, str, int]:
    """Cheapest fleet choice for moving qty over km. Returns (cost Rs, vehicle, trips)."""
    best = None
    for v in VEHICLES:
        trips = max(1, math.ceil(qty_qtl / v.capacity_qtl))
        cost = trips * (v.rate_per_km * km * RETURN_FACTOR + LOADING_FEE)
        if best is None or cost < best[0]:
            best = (round(cost, 0), v.name, trips)
    return best


def spoilage_fraction(k: float, days_wait: float, km: float, avg_temp_c: float = 25.0) -> float:
    """Exponential quality decay: share of the lot lost before sale.

    k is the crop's daily decay rate at 25°C; temperature scales it with a Q10 rule.
    Exposure = days held before the trip + transit time.
    """
    rate = k * Q10 ** ((avg_temp_c - 25.0) / 10.0)
    exposure = max(0.0, days_wait) + transit_hours(km) / 24.0
    return 1.0 - math.exp(-rate * exposure)


def solve_route(depot: tuple[float, float], stops: list[tuple[float, float]], time_limit_s: int = 2) -> tuple[list[int], float]:
    """Shortest round trip from depot through all stops (TSP via OR-Tools routing).

    Returns (visit order as indices into `stops`, total road km).
    """
    if not stops:
        return [], 0.0
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    pts = [depot, *stops]
    n = len(pts)
    dist = [[int(road_km(*pts[i], *pts[j]) * 10) for j in range(n)] for i in range(n)]
    mgr = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(mgr)
    cb = routing.RegisterTransitCallback(lambda a, b: dist[mgr.IndexToNode(a)][mgr.IndexToNode(b)])
    routing.SetArcCostEvaluatorOfAllVehicles(cb)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = time_limit_s
    sol = routing.SolveWithParameters(params)
    order, idx, total = [], routing.Start(0), 0
    while not routing.IsEnd(idx):
        nxt = sol.Value(routing.NextVar(idx))
        total += dist[mgr.IndexToNode(idx)][mgr.IndexToNode(nxt)]
        if mgr.IndexToNode(idx) != 0:
            order.append(mgr.IndexToNode(idx) - 1)
        idx = nxt
    return order, total / 10.0
