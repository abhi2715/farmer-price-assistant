"""Marketplace matching engine.

Hard constraints (all must hold):
  * same crop; lot grade >= demand's minimum grade (A > B > C)
  * road distance <= the buyer's max distance
  * landed cost = farmer ask + transport/qtl <= buyer's max price
  * lot available on/before the buyer's needed-by date; match >= MIN_MATCH_QTL
Soft score (0..1): price surplus 40%, quantity fit 30%, proximity 20%, grade bonus 10%.
Greedy assignment by descending score with partial fills; the deal price splits the surplus
evenly between farmer and buyer:  price = ask + (max_price - landed_cost) / 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.logistics import road_km, transport_cost

GRADE_RANK = {"A": 3, "B": 2, "C": 1}
MIN_MATCH_QTL = 1.0
W_PRICE, W_QTY, W_DIST, W_GRADE = 0.4, 0.3, 0.2, 0.1


@dataclass
class LotIn:
    id: int
    crop_id: int
    grade: str
    remaining_qtl: float
    ask_price: float
    lat: float
    lon: float
    available_from: date


@dataclass
class DemandIn:
    id: int
    crop_id: int
    min_grade: str
    remaining_qtl: float
    max_price: float
    lat: float
    lon: float
    max_distance_km: float
    needed_by: date


@dataclass
class Proposal:
    lot_id: int
    demand_id: int
    quantity_qtl: float
    price_per_qtl: float
    distance_km: float
    transport_per_qtl: float
    score: float


def score_pair(lot: LotIn, dem: DemandIn) -> Proposal | None:
    if lot.crop_id != dem.crop_id:
        return None
    if GRADE_RANK[lot.grade] < GRADE_RANK[dem.min_grade]:
        return None
    if lot.available_from > dem.needed_by:
        return None
    km = road_km(lot.lat, lot.lon, dem.lat, dem.lon)
    if km > dem.max_distance_km:
        return None
    qty = min(lot.remaining_qtl, dem.remaining_qtl)
    if qty < MIN_MATCH_QTL:
        return None
    t_per_qtl = transport_cost(qty, km)[0] / qty
    landed = lot.ask_price + t_per_qtl
    surplus = dem.max_price - landed
    if surplus < 0:
        return None
    price = lot.ask_price + surplus / 2
    s_price = min(1.0, surplus / max(dem.max_price, 1) / 0.2)  # 20% surplus => full marks
    s_qty = qty / max(lot.remaining_qtl, dem.remaining_qtl)
    s_dist = 1 - km / max(dem.max_distance_km, 1)
    s_grade = (GRADE_RANK[lot.grade] - GRADE_RANK[dem.min_grade]) / 2
    score = W_PRICE * s_price + W_QTY * s_qty + W_DIST * s_dist + W_GRADE * s_grade
    return Proposal(lot.id, dem.id, round(qty, 2), round(price, 0), km, round(t_per_qtl, 1), round(score, 4))


def match(lots: list[LotIn], demands: list[DemandIn], exclude: set[tuple[int, int]] | None = None) -> list[Proposal]:
    """Greedy max-score matching with partial fills. Mutates remaining quantities on the inputs."""
    exclude = exclude or set()
    cands = []
    for lot in lots:
        for dem in demands:
            if (lot.id, dem.id) in exclude:
                continue
            p = score_pair(lot, dem)
            if p:
                cands.append(p)
    cands.sort(key=lambda p: (-p.score, p.lot_id, p.demand_id))
    lot_by, dem_by = {lot.id: lot for lot in lots}, {d.id: d for d in demands}
    out = []
    for p in cands:
        lot, dem = lot_by[p.lot_id], dem_by[p.demand_id]
        qty = min(lot.remaining_qtl, dem.remaining_qtl)
        if qty < MIN_MATCH_QTL:
            continue
        if qty != p.quantity_qtl:  # partially consumed by an earlier match -> re-price for the new qty
            p = score_pair(LotIn(**{**lot.__dict__, "remaining_qtl": qty}), DemandIn(**{**dem.__dict__, "remaining_qtl": qty}))
            if p is None:
                continue
        lot.remaining_qtl = round(lot.remaining_qtl - p.quantity_qtl, 2)
        dem.remaining_qtl = round(dem.remaining_qtl - p.quantity_qtl, 2)
        out.append(p)
    return out


@dataclass
class Commission:
    gross_amount: float
    farmer_commission: float
    buyer_commission: float
    platform_revenue: float
    farmer_payout: float
    buyer_total: float


def commission(qty: float, price: float, farmer_pct: float, buyer_pct: float) -> Commission:
    gross = round(qty * price, 2)
    fc = round(gross * farmer_pct / 100, 2)
    bc = round(gross * buyer_pct / 100, 2)
    return Commission(gross, fc, bc, round(fc + bc, 2), round(gross - fc, 2), round(gross + bc, 2))
