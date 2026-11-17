"""Lots (farmers), demands (buyers), matches, transactions and the buyer pickup route."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Demand, Lot, Match, Transaction, User
from app.schemas import DemandIn, LotIn, MatchAction
from app.security import current_user, require
from app.services import marketplace
from app.services.logistics import solve_route

router = APIRouter(tags=["marketplace"])


def lot_out(lot: Lot) -> dict:
    return {"id": lot.id, "crop_id": lot.crop_id, "crop": lot.crop.name_en, "emoji": lot.crop.emoji, "grade": lot.grade,
            "quantity_qtl": lot.quantity_qtl, "remaining_qtl": lot.remaining_qtl, "ask_price": lot.ask_price,
            "available_from": lot.available_from.isoformat(), "status": lot.status, "created_at": lot.created_at.isoformat(),
            "lat": lot.lat, "lon": lot.lon}


def demand_out(d: Demand) -> dict:
    return {"id": d.id, "crop_id": d.crop_id, "crop": d.crop.name_en, "emoji": d.crop.emoji, "min_grade": d.min_grade,
            "quantity_qtl": d.quantity_qtl, "remaining_qtl": d.remaining_qtl, "max_price": d.max_price,
            "max_distance_km": d.max_distance_km, "needed_by": d.needed_by.isoformat(), "status": d.status,
            "created_at": d.created_at.isoformat()}


def match_out(m: Match, viewer: User) -> dict:
    lot, dem = m.lot, m.demand
    d = {"id": m.id, "status": m.status, "quantity_qtl": m.quantity_qtl, "price_per_qtl": m.price_per_qtl,
         "distance_km": m.distance_km, "transport_per_qtl": m.transport_per_qtl, "score": m.score,
         "farmer_accepted": m.farmer_accepted, "buyer_accepted": m.buyer_accepted,
         "crop": lot.crop.name_en, "emoji": lot.crop.emoji, "grade": lot.grade, "lot_id": lot.id, "demand_id": dem.id,
         "created_at": m.created_at.isoformat(), "value": round(m.quantity_qtl * m.price_per_qtl)}
    # Contact details are shared only once both sides accept.
    if viewer.role in ("farmer", "admin"):
        d["buyer"] = {"name": dem.buyer.business_name, "type": dem.buyer.buyer_type}
        if m.status == "accepted" or viewer.role == "admin":
            d["buyer"]["phone"] = dem.buyer.user.phone
    if viewer.role in ("buyer", "admin"):
        d["farmer"] = {"name": lot.farmer.user.name, "village": lot.farmer.village, "lat": lot.lat, "lon": lot.lon}
        if m.status == "accepted" or viewer.role == "admin":
            d["farmer"]["phone"] = lot.farmer.user.phone
    return d


# ----- farmer lots ----------------------------------------------------------------------------
@router.post("/lots", status_code=201)
def create_lot(body: LotIn, user: User = Depends(require("farmer")), db: Session = Depends(get_db)):
    f = user.farmer
    lot = Lot(farmer_id=f.id, crop_id=body.crop_id, grade=body.grade, quantity_qtl=body.quantity_qtl,
              remaining_qtl=body.quantity_qtl, ask_price=body.ask_price,
              lat=body.lat if body.lat is not None else f.lat, lon=body.lon if body.lon is not None else f.lon,
              available_from=body.available_from or date.today())
    db.add(lot)
    db.commit()
    # Match immediately so the farmer sees buyers right away; the periodic job catches the rest.
    matches = marketplace.run_matching(db, lot_ids=[lot.id])
    db.refresh(lot)
    return {"lot": lot_out(lot), "matches": [match_out(m, user) for m in matches]}


@router.get("/lots/mine")
def my_lots(user: User = Depends(require("farmer")), db: Session = Depends(get_db)):
    lots = db.scalars(select(Lot).where(Lot.farmer_id == user.farmer.id).order_by(Lot.id.desc())).all()
    out = []
    for lot in lots:
        d = lot_out(lot)
        d["matches"] = [match_out(m, user) for m in db.scalars(select(Match).where(Match.lot_id == lot.id).order_by(Match.score.desc()))]
        out.append(d)
    return out


@router.delete("/lots/{lot_id}")
def cancel_lot(lot_id: int, user: User = Depends(require("farmer")), db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot or lot.farmer_id != user.farmer.id:
        raise HTTPException(404, "lot not found")
    if lot.status == "sold":
        raise HTTPException(409, "lot already sold")
    for m in db.scalars(select(Match).where(Match.lot_id == lot.id, Match.status == "proposed")):
        marketplace.respond(db, m, "farmer", accept=False)
    lot.status = "cancelled"
    db.commit()
    return lot_out(lot)


# ----- buyer demands --------------------------------------------------------------------------
@router.post("/demands", status_code=201)
def create_demand(body: DemandIn, user: User = Depends(require("buyer")), db: Session = Depends(get_db)):
    b = user.buyer
    d = Demand(buyer_id=b.id, crop_id=body.crop_id, min_grade=body.min_grade, quantity_qtl=body.quantity_qtl,
               remaining_qtl=body.quantity_qtl, max_price=body.max_price, max_distance_km=body.max_distance_km,
               needed_by=body.needed_by, lat=body.lat if body.lat is not None else b.lat,
               lon=body.lon if body.lon is not None else b.lon)
    db.add(d)
    db.commit()
    open_lots = [i for (i,) in db.execute(select(Lot.id).where(Lot.crop_id == d.crop_id, Lot.status.in_(marketplace.OPEN)))]
    matches = marketplace.run_matching(db, lot_ids=open_lots, demand_ids=[d.id]) if open_lots else []
    db.refresh(d)
    return {"demand": demand_out(d), "matches": [match_out(m, user) for m in matches]}


@router.get("/demands/mine")
def my_demands(user: User = Depends(require("buyer")), db: Session = Depends(get_db)):
    return [demand_out(d) for d in db.scalars(select(Demand).where(Demand.buyer_id == user.buyer.id).order_by(Demand.id.desc()))]


@router.delete("/demands/{demand_id}")
def cancel_demand(demand_id: int, user: User = Depends(require("buyer")), db: Session = Depends(get_db)):
    d = db.get(Demand, demand_id)
    if not d or d.buyer_id != user.buyer.id:
        raise HTTPException(404, "demand not found")
    for m in db.scalars(select(Match).where(Match.demand_id == d.id, Match.status == "proposed")):
        marketplace.respond(db, m, "buyer", accept=False)
    d.status = "cancelled"
    db.commit()
    return demand_out(d)


# ----- matches & transactions -------------------------------------------------------------------
def _my_matches_q(user: User):
    q = select(Match).join(Lot, Lot.id == Match.lot_id).join(Demand, Demand.id == Match.demand_id)
    if user.role == "farmer":
        return q.where(Lot.farmer_id == user.farmer.id)
    if user.role == "buyer":
        return q.where(Demand.buyer_id == user.buyer.id)
    return q


@router.get("/matches/mine")
def my_matches(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [match_out(m, user) for m in db.scalars(_my_matches_q(user).order_by(Match.id.desc()))]


@router.post("/matches/{match_id}/respond")
def respond(match_id: int, body: MatchAction, user: User = Depends(require("farmer", "buyer")), db: Session = Depends(get_db)):
    m = db.scalar(_my_matches_q(user).where(Match.id == match_id))
    if not m:
        raise HTTPException(404, "match not found")
    try:
        m = marketplace.respond(db, m, user.role, body.accept)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return match_out(m, user)


@router.get("/transactions/mine")
def my_transactions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Transaction).order_by(Transaction.id.desc())
    if user.role == "farmer":
        q = q.where(Transaction.farmer_id == user.farmer.id)
    elif user.role == "buyer":
        q = q.where(Transaction.buyer_id == user.buyer.id)
    out = []
    for t in db.scalars(q):
        d = {c: getattr(t, c) for c in ("id", "match_id", "quantity_qtl", "price_per_qtl", "gross_amount", "farmer_commission",
                                         "buyer_commission", "platform_revenue", "farmer_payout", "buyer_total", "status")}
        d["crop"], d["created_at"] = t.crop.name_en, t.created_at.isoformat()
        out.append(d)
    return out


@router.get("/buyer/route")
def pickup_route(user: User = Depends(require("buyer")), db: Session = Depends(get_db)):
    """Optimal pickup tour over the farms of this buyer's accepted (and proposed) matches."""
    ms = db.scalars(_my_matches_q(user).where(or_(Match.status == "accepted", Match.status == "proposed"))).all()
    stops = [(m.lot.lat, m.lot.lon) for m in ms]
    order, km = solve_route((user.buyer.lat, user.buyer.lon), stops)
    return {"depot": {"lat": user.buyer.lat, "lon": user.buyer.lon, "name": user.buyer.business_name},
            "total_km": km, "solver": "OR-Tools routing (TSP)",
            "stops": [dict(match_id=ms[i].id, crop=ms[i].lot.crop.name_en, quantity_qtl=ms[i].quantity_qtl,
                           farmer=ms[i].lot.farmer.user.name, village=ms[i].lot.farmer.village,
                           lat=ms[i].lot.lat, lon=ms[i].lot.lon, status=ms[i].status) for i in order]}
