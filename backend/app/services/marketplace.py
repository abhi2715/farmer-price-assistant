"""DB side of the marketplace: run matching, accept/reject matches, settle into transactions."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Demand, Lot, Match, Transaction
from app.services import matcher
from app.services.notify import create_alert

OPEN = ("open", "partially_matched")


def _status(remaining: float, total: float) -> str:
    if remaining < matcher.MIN_MATCH_QTL:
        return "matched"
    return "partially_matched" if remaining < total else "open"


def run_matching(db: Session, lot_ids: list[int] | None = None, demand_ids: list[int] | None = None) -> list[Match]:
    lq = select(Lot).where(Lot.status.in_(OPEN))
    dq = select(Demand).where(Demand.status.in_(OPEN))
    if lot_ids:
        lq = lq.where(Lot.id.in_(lot_ids))
    if demand_ids:
        dq = dq.where(Demand.id.in_(demand_ids))
    lots = db.scalars(lq.with_for_update(skip_locked=True) if db.get_bind().dialect.name == "postgresql" else lq).all()
    if not lots:
        return []
    dems = db.scalars(dq.where(Demand.crop_id.in_({lot.crop_id for lot in lots}))).all()
    existing = set(db.execute(select(Match.lot_id, Match.demand_id)).all())
    lin = [matcher.LotIn(lot.id, lot.crop_id, lot.grade, lot.remaining_qtl, lot.ask_price, lot.lat, lot.lon, lot.available_from) for lot in lots]
    din = [matcher.DemandIn(d.id, d.crop_id, d.min_grade, d.remaining_qtl, d.max_price, d.lat, d.lon, d.max_distance_km, d.needed_by) for d in dems]
    props = matcher.match(lin, din, exclude=existing)
    lot_by, dem_by = {lot.id: lot for lot in lots}, {d.id: d for d in dems}
    created = []
    for p in props:
        lot, dem = lot_by[p.lot_id], dem_by[p.demand_id]
        m = Match(lot_id=p.lot_id, demand_id=p.demand_id, quantity_qtl=p.quantity_qtl, price_per_qtl=p.price_per_qtl,
                  distance_km=p.distance_km, transport_per_qtl=p.transport_per_qtl, score=p.score)
        db.add(m)
        lot.remaining_qtl = round(lot.remaining_qtl - p.quantity_qtl, 2)
        dem.remaining_qtl = round(dem.remaining_qtl - p.quantity_qtl, 2)
        lot.status = _status(lot.remaining_qtl, lot.quantity_qtl)
        dem.status = _status(dem.remaining_qtl, dem.quantity_qtl)
        db.flush()
        create_alert(db, lot.farmer.user, "match", f"match:{m.id}:f", lot.crop_id, None,
                     {"qty": p.quantity_qtl, "price": p.price_per_qtl, "buyer": dem.buyer.business_name})
        create_alert(db, dem.buyer.user, "match_buyer", f"match:{m.id}:b", lot.crop_id, None,
                     {"qty": p.quantity_qtl, "price": p.price_per_qtl, "km": round(p.distance_km)}, push=False)
        created.append(m)
    db.commit()
    return created


def _release(db: Session, m: Match) -> None:
    lot, dem = m.lot, m.demand
    lot.remaining_qtl = round(lot.remaining_qtl + m.quantity_qtl, 2)
    dem.remaining_qtl = round(dem.remaining_qtl + m.quantity_qtl, 2)
    if lot.status != "cancelled":
        lot.status = _status(lot.remaining_qtl, lot.quantity_qtl)
    if dem.status != "cancelled":
        dem.status = _status(dem.remaining_qtl, dem.quantity_qtl)


def respond(db: Session, m: Match, side: str, accept: bool) -> Match:
    """side is 'farmer' or 'buyer'. Both accepting confirms the deal and books commission."""
    if m.status != "proposed":
        raise ValueError(f"match is {m.status}")
    if not accept:
        m.status = "rejected"
        _release(db, m)
        db.commit()
        return m
    if side == "farmer":
        m.farmer_accepted = True
    else:
        m.buyer_accepted = True
    if m.farmer_accepted and m.buyer_accepted:
        s = get_settings()
        c = matcher.commission(m.quantity_qtl, m.price_per_qtl, s.farmer_commission_pct, s.buyer_commission_pct)
        m.status = "accepted"
        db.add(Transaction(match_id=m.id, farmer_id=m.lot.farmer_id, buyer_id=m.demand.buyer_id, crop_id=m.lot.crop_id,
                           quantity_qtl=m.quantity_qtl, price_per_qtl=m.price_per_qtl, **c.__dict__))
        if m.lot.remaining_qtl < matcher.MIN_MATCH_QTL and all(
            x.status != "proposed" or x.id == m.id for x in db.scalars(select(Match).where(Match.lot_id == m.lot_id))
        ):
            m.lot.status = "sold"
        db.flush()
        create_alert(db, m.lot.farmer.user, "deal", f"deal:{m.id}:f", m.lot.crop_id, None,
                     {"qty": m.quantity_qtl, "price": m.price_per_qtl, "amount": c.farmer_payout})
        create_alert(db, m.demand.buyer.user, "deal_buyer", f"deal:{m.id}:b", m.lot.crop_id, None,
                     {"qty": m.quantity_qtl, "price": m.price_per_qtl, "amount": c.buyer_total}, push=False)
    db.commit()
    return m
