"""Sell-decision optimizer.

For every (mandi, sell date) option:
    net = forecast_price x qty  - transport - mandi fees - spoilage loss - holding cost
Options are ranked by expected net; the 80%-interval lower bound gives a "worst case".
For large lots an OR-Tools MIP splits the quantity across mandi-days, because a single mandi
can only absorb a fraction of its normal daily arrivals before the price drops.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from app.services.logistics import VEHICLES, road_km, spoilage_fraction, transit_hours, transport_cost

CAPITAL_COST_ANNUAL = 0.12  # farmer's cost of waiting for cash (informal credit rates are higher)
MAX_SPOILAGE = 0.35  # options losing more than this are never recommended
ABSORB_FRACTION = 0.05  # one seller can move ~5% of a mandi's daily arrivals without denting price


@dataclass
class MandiInfo:
    id: int
    name: str
    lat: float
    lon: float
    market_fee_pct: float
    commission_pct: float
    hamali_per_qtl: float
    daily_arrivals_qtl: float = 1000.0


@dataclass
class CropInfo:
    id: int
    code: str
    perishability_k: float
    storage_cost_per_qtl_day: float


@dataclass
class Option:
    mandi_id: int
    mandi_name: str
    sell_date: date
    days_wait: int
    distance_km: float
    transit_hours: float
    price: float
    price_lo: float
    price_hi: float
    gross: float
    transport: float
    vehicle: str
    trips: int
    fees: float
    spoilage_pct: float
    spoilage_loss: float
    holding_cost: float
    net: float
    net_lo: float
    net_per_qtl: float
    horizon: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sell_date"] = self.sell_date.isoformat()
        return d


PriceFn = Callable[[int, date], "tuple[float, float, float, int] | None"]  # (yhat, lo, hi, horizon)
TempFn = Callable[[int, date, date], float]


def evaluate_option(crop: CropInfo, qty: float, origin: tuple[float, float], m: MandiInfo, sell_date: date,
                    today: date, price: tuple[float, float, float, int], avg_temp: float) -> Option:
    yhat, lo, hi, h = price
    km = road_km(origin[0], origin[1], m.lat, m.lon)
    days = (sell_date - today).days
    spoil = spoilage_fraction(crop.perishability_k, days, km, avg_temp)
    gross = yhat * qty
    t_cost, vehicle, trips = transport_cost(qty, km)
    saleable = qty * (1 - spoil)
    fees = (m.market_fee_pct + m.commission_pct) / 100 * yhat * saleable + m.hamali_per_qtl * saleable
    spoil_loss = yhat * qty * spoil
    holding = crop.storage_cost_per_qtl_day * qty * days + yhat * qty * CAPITAL_COST_ANNUAL / 365 * days
    net = gross - t_cost - fees - spoil_loss - holding
    fee_rate = (m.market_fee_pct + m.commission_pct) / 100
    net_lo = lo * saleable * (1 - fee_rate) - m.hamali_per_qtl * saleable - t_cost - holding
    return Option(
        mandi_id=m.id, mandi_name=m.name, sell_date=sell_date, days_wait=days, distance_km=km,
        transit_hours=round(transit_hours(km), 1), price=round(yhat, 0), price_lo=round(lo, 0), price_hi=round(hi, 0),
        gross=round(gross, 0), transport=t_cost, vehicle=vehicle, trips=trips, fees=round(fees, 0),
        spoilage_pct=round(spoil * 100, 2), spoilage_loss=round(spoil_loss, 0), holding_cost=round(holding, 0),
        net=round(net, 0), net_lo=round(net_lo, 0), net_per_qtl=round(net / qty, 1), horizon=h,
    )


def rank_options(crop: CropInfo, qty: float, origin: tuple[float, float], mandis: list[MandiInfo],
                 price_fn: PriceFn, temp_fn: TempFn, today: date, max_wait_days: int = 14) -> list[Option]:
    opts = []
    for m in mandis:
        for d in range(0, max_wait_days + 1):
            sd = today + timedelta(days=d)
            p = price_fn(m.id, sd)
            if p is None:
                continue
            o = evaluate_option(crop, qty, origin, m, sd, today, p, temp_fn(m.id, today, sd))
            if o.spoilage_pct / 100 <= MAX_SPOILAGE:
                opts.append(o)
    opts.sort(key=lambda o: o.net, reverse=True)
    return opts


@dataclass
class SplitPlan:
    allocations: list[dict] = field(default_factory=list)
    total_net: float = 0.0
    single_best_net: float = 0.0
    solver: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def split_plan(crop: CropInfo, qty: float, origin: tuple[float, float], options: list[Option],
               mandis: dict[int, MandiInfo], today: date, top_k: int = 20) -> SplitPlan | None:
    """MIP: allocate qty over the best mandi-day options under absorption caps and per-trip costs.

    max  sum_i u_i * x_i - c_i * n_i
    s.t. x_i <= cap_i,  x_i <= vcap * n_i,  sum_i x_i = qty,  x >= 0, n integer >= 0
    where u_i is the per-quintal net excluding transport and c_i the cost of one truck trip.
    """
    from ortools.linear_solver import pywraplp

    cands, seen = [], set()
    for o in options:  # keep the best day per mandi plus a few alternates
        if len(cands) >= top_k:
            break
        if (o.mandi_id, o.sell_date) in seen:
            continue
        seen.add((o.mandi_id, o.sell_date))
        cands.append(o)
    if not cands:
        return None
    caps = [ABSORB_FRACTION * mandis[o.mandi_id].daily_arrivals_qtl for o in cands]
    if qty <= caps[0]:
        return None  # the single best option can absorb the whole lot - no split needed
    solver = pywraplp.Solver.CreateSolver("SCIP") or pywraplp.Solver.CreateSolver("CBC")
    truck = VEHICLES[-1]
    xs, ns, unit, trip = [], [], [], []
    for i, o in enumerate(cands):
        u = (o.net + o.transport) / qty  # per-qtl value before transport
        c = truck.rate_per_km * o.distance_km * 1.6 + 300
        unit.append(u)
        trip.append(c)
        xs.append(solver.NumVar(0, caps[i], f"x{i}"))
        ns.append(solver.IntVar(0, math.ceil(caps[i] / truck.capacity_qtl) + 1, f"n{i}"))
        solver.Add(xs[i] <= truck.capacity_qtl * ns[i])
    # A "same-day local spot sale" slack absorbs anything that does not fit, at the worst option's value
    slack = solver.NumVar(0, qty, "slack")
    worst_unit = min(unit) * 0.85
    solver.Add(sum(xs) + slack == qty)
    solver.Maximize(sum(u * x for u, x in zip(unit, xs)) - sum(c * n for c, n in zip(trip, ns)) + worst_unit * slack)
    solver.SetTimeLimit(3000)
    if solver.Solve() not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return None
    allocs = []
    for i, o in enumerate(cands):
        q = xs[i].solution_value()
        if q > 0.01:
            allocs.append(dict(mandi_id=o.mandi_id, mandi_name=o.mandi_name, sell_date=o.sell_date.isoformat(),
                               quantity_qtl=round(q, 1), trucks=int(round(ns[i].solution_value())),
                               price=o.price, net=round(unit[i] * q - trip[i] * ns[i].solution_value(), 0)))
    if slack.solution_value() > 0.01:
        allocs.append(dict(mandi_id=None, mandi_name="local spot sale", sell_date=today.isoformat(),
                           quantity_qtl=round(slack.solution_value(), 1), trucks=0, price=None,
                           net=round(worst_unit * slack.solution_value(), 0)))
    allocs.sort(key=lambda a: -a["quantity_qtl"])
    return SplitPlan(allocations=allocs, total_net=round(solver.Objective().Value(), 0),
                     single_best_net=cands[0].net, solver=solver.SolverVersion().split()[0])
