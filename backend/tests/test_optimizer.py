from datetime import date, timedelta

import pytest

from app.services.logistics import haversine_km, road_km, solve_route, spoilage_fraction, transport_cost
from app.services.optimizer import MAX_SPOILAGE, CropInfo, MandiInfo, evaluate_option, rank_options, split_plan

TODAY = date(2026, 1, 10)
TOMATO = CropInfo(1, "tomato", 0.06, 0.0)
RAGI = CropInfo(2, "ragi", 0.0004, 0.6)
FARM = (13.34, 78.21)
NEAR = MandiInfo(1, "Near", 13.14, 78.13, 1.0, 5.0, 20, daily_arrivals_qtl=3000)
FAR = MandiInfo(2, "Far", 13.03, 77.54, 1.0, 5.0, 20, daily_arrivals_qtl=3000)


def flat(prices: dict[int, float], slope: float = 0.0):
    def fn(mid, d):
        h = (d - TODAY).days
        p = prices[mid] * (1 + slope * h)
        return (p, p * 0.9, p * 1.1, h)

    return fn


def temp25(*_):
    return 25.0


def test_haversine_known_distance():
    # Bengaluru -> Mysuru is ~128 km great-circle
    assert 120 < haversine_km(12.97, 77.59, 12.30, 76.65) < 135
    assert road_km(12.97, 77.59, 12.30, 76.65) == pytest.approx(haversine_km(12.97, 77.59, 12.30, 76.65) * 1.3, rel=0.01)


def test_spoilage_monotonic_and_temperature_sensitive():
    a = spoilage_fraction(0.06, 0, 50)
    b = spoilage_fraction(0.06, 5, 50)
    c = spoilage_fraction(0.06, 5, 50, avg_temp_c=35)
    assert 0 < a < b < c < 1
    assert c == pytest.approx(1 - (1 - b) ** 2, rel=0.05)  # Q10=2 => rate doubles at +10C
    assert spoilage_fraction(0.0004, 5, 50) < 0.005  # grains barely decay


def test_transport_chooses_cheapest_fleet():
    cost, vehicle, trips = transport_cost(8, 100)
    assert vehicle == "pickup" and trips == 1
    cost_b, vehicle_b, trips_b = transport_cost(150, 100)
    assert vehicle_b == "truck" and trips_b == 2
    assert cost_b > cost


def test_net_profit_identity():
    o = evaluate_option(TOMATO, 50, FARM, NEAR, TODAY + timedelta(days=2), TODAY, (2000, 1800, 2200, 2), 28)
    assert o.net == pytest.approx(o.gross - o.transport - o.fees - o.spoilage_loss - o.holding_cost, abs=2)
    assert o.net_lo < o.net
    assert o.spoilage_pct > 0 and o.days_wait == 2


def test_perishable_with_flat_prices_sells_today():
    opts = rank_options(TOMATO, 40, FARM, [NEAR], flat({1: 2000}), temp25, TODAY, 10)
    assert opts[0].days_wait == 0
    assert all(o.spoilage_pct / 100 <= MAX_SPOILAGE for o in opts)


def test_storable_crop_waits_for_rising_price():
    opts = rank_options(RAGI, 40, FARM, [NEAR], flat({1: 4000}, slope=0.01), temp25, TODAY, 10)
    assert opts[0].days_wait == 10  # +1%/day beats storage + capital cost


def test_far_mandi_wins_only_when_premium_beats_transport():
    small = rank_options(RAGI, 40, FARM, [NEAR, FAR], flat({1: 4000, 2: 4010}), temp25, TODAY, 0)
    assert small[0].mandi_id == NEAR.id
    big = rank_options(RAGI, 40, FARM, [NEAR, FAR], flat({1: 4000, 2: 4600}), temp25, TODAY, 0)
    assert big[0].mandi_id == FAR.id


def test_ranking_sorted_by_net():
    opts = rank_options(TOMATO, 40, FARM, [NEAR, FAR], flat({1: 2000, 2: 2300}, 0.01), temp25, TODAY, 7)
    nets = [o.net for o in opts]
    assert nets == sorted(nets, reverse=True)


def test_split_plan_spreads_large_lot():
    mandis = {1: NEAR, 2: FAR}
    qty = 400  # caps are 5% of 3000 = 150 qtl per mandi-day
    opts = rank_options(RAGI, qty, FARM, [NEAR, FAR], flat({1: 4000, 2: 4100}), temp25, TODAY, 3)
    plan = split_plan(RAGI, qty, FARM, opts, mandis, TODAY)
    assert plan is not None
    assert sum(a["quantity_qtl"] for a in plan.allocations) == pytest.approx(qty, abs=0.5)
    assert len([a for a in plan.allocations if a["mandi_id"]]) >= 2
    assert all(a["quantity_qtl"] <= 150.01 for a in plan.allocations if a["mandi_id"])


def test_no_split_for_small_lot():
    opts = rank_options(RAGI, 20, FARM, [NEAR], flat({1: 4000}), temp25, TODAY, 2)
    assert split_plan(RAGI, 20, FARM, opts, {1: NEAR}, TODAY) is None


def test_route_is_optimal_permutation():
    depot = (12.97, 77.59)
    stops = [(13.34, 78.21), (12.30, 76.65), (13.14, 78.13), (12.95, 77.0)]
    order, km = solve_route(depot, stops)
    assert sorted(order) == list(range(len(stops)))
    naive = road_km(*depot, *stops[0]) + sum(road_km(*stops[i], *stops[i + 1]) for i in range(3)) + road_km(*stops[3], *depot)
    assert km <= naive + 0.5
