from datetime import date, timedelta

import pytest

from app.services.matcher import DemandIn, LotIn, commission, match, score_pair

D = date(2026, 1, 10)


def lot(id=1, crop=1, grade="B", qty=50, ask=2000, lat=13.14, lon=78.13, avail=D):
    return LotIn(id, crop, grade, qty, ask, lat, lon, avail)


def dem(id=1, crop=1, grade="B", qty=50, maxp=2400, lat=12.99, lon=77.57, km=150, by=D + timedelta(days=7)):
    return DemandIn(id, crop, grade, qty, maxp, lat, lon, km, by)


def test_basic_match_splits_surplus():
    p = score_pair(lot(), dem())
    assert p is not None
    landed = 2000 + p.transport_per_qtl
    assert p.price_per_qtl == pytest.approx(2000 + (2400 - landed) / 2, abs=1)
    assert 2000 < p.price_per_qtl < 2400
    assert 0 < p.score <= 1


@pytest.mark.parametrize("lt,d", [
    (lot(crop=2), dem()),                       # crop mismatch
    (lot(grade="C"), dem(grade="B")),           # grade below minimum
    (lot(), dem(km=20)),                         # too far
    (lot(ask=2390), dem(maxp=2400)),            # transport makes it unaffordable
    (lot(avail=D + timedelta(days=30)), dem()), # not available in time
    (lot(qty=0.5), dem()),                      # below minimum match size
])
def test_hard_constraints(lt, d):
    assert score_pair(lt, d) is None


def test_better_grade_is_allowed():
    assert score_pair(lot(grade="A"), dem(grade="C")) is not None


def test_partial_fill_across_two_demands():
    lots = [lot(qty=100)]
    dems = [dem(id=1, qty=60), dem(id=2, qty=60, maxp=2350)]
    out = match(lots, dems)
    assert sum(p.quantity_qtl for p in out) == pytest.approx(100)
    assert lots[0].remaining_qtl == pytest.approx(0)
    assert {p.demand_id for p in out} == {1, 2}


def test_greedy_prefers_higher_score():
    lots = [lot(qty=50)]
    dems = [dem(id=1, maxp=2200), dem(id=2, maxp=2600)]
    out = match(lots, dems)
    assert out[0].demand_id == 2  # higher price surplus wins the full lot
    assert len(out) == 1


def test_exclude_existing_pairs():
    assert match([lot()], [dem()], exclude={(1, 1)}) == []


def test_commission_math():
    c = commission(10, 2000, 0.5, 1.5)
    assert c.gross_amount == 20000
    assert c.farmer_commission == 100 and c.buyer_commission == 300
    assert c.platform_revenue == 400
    assert c.farmer_payout == 19900 and c.buyer_total == 20300
