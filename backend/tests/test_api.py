from sqlalchemy import select

from app.models import Crop, Mandi
from tests.conftest import ADMIN, BUYER, FARMER, login

API = "/api/v1"


def crop_id(db, code):
    return db.scalar(select(Crop.id).where(Crop.code == code))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["db"] is True and r.json()["model"]


def test_otp_flow_and_bad_otp(client):
    r = client.post(f"{API}/auth/otp/request", json={"phone": "9876543210"})
    assert r.json()["dev_otp"] == "123456"
    assert client.post(f"{API}/auth/otp/verify", json={"phone": "9876543210", "otp": "000000"}).status_code == 401
    r = client.post(f"{API}/auth/otp/verify", json={"phone": "9876543210", "otp": "123456", "role": "farmer", "name": "New"})
    assert r.status_code == 200 and r.json()["created"] and r.json()["user"]["role"] == "farmer"
    # OTP is single-use
    assert client.post(f"{API}/auth/otp/verify", json={"phone": "9876543210", "otp": "123456"}).status_code == 401


def test_otp_attempt_limit(client):
    client.post(f"{API}/auth/otp/request", json={"phone": "9876500000"})
    for _ in range(5):
        client.post(f"{API}/auth/otp/verify", json={"phone": "9876500000", "otp": "111111"})
    r = client.post(f"{API}/auth/otp/verify", json={"phone": "9876500000", "otp": "123456"})
    assert r.status_code == 401  # locked out after 5 wrong attempts


def test_cannot_self_register_admin(client):
    client.post(f"{API}/auth/otp/request", json={"phone": "9876511111"})
    r = client.post(f"{API}/auth/otp/verify", json={"phone": "9876511111", "otp": "123456", "role": "admin"})
    assert r.status_code == 422


def test_validation_errors(client):
    r = client.post(f"{API}/auth/otp/request", json={"phone": "12345"})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "phone"
    h = login(client, FARMER)
    assert client.post(f"{API}/lots", headers=h, json={"crop_id": 1, "quantity_qtl": -3, "ask_price": 100}).status_code == 422
    assert client.post(f"{API}/lots", headers=h, json={"crop_id": 1, "quantity_qtl": 3, "ask_price": 100, "hack": 1}).status_code == 422
    assert client.post(f"{API}/recommend", headers=h, json={"crop_id": 1, "quantity_qtl": 5, "lat": 51.5, "lon": 0.1}).status_code == 422


def test_rate_limit_on_otp(client):
    codes = [client.post(f"{API}/auth/otp/request", json={"phone": "9876522222"}).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and 429 in codes[5:]


def test_auth_and_roles(client):
    assert client.get(f"{API}/me").status_code == 401
    assert client.get(f"{API}/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    hf = login(client, FARMER)
    assert client.post(f"{API}/demands", headers=hf, json={"crop_id": 1, "quantity_qtl": 5, "max_price": 100}).status_code == 403
    assert client.get(f"{API}/admin/summary", headers=hf).status_code == 403


def test_catalog(client):
    crops = client.get(f"{API}/crops").json()
    assert len(crops) == 10 and {"name_en", "name_hi", "name_kn"} <= set(crops[0])
    ms = client.get(f"{API}/mandis", params={"lat": 13.3, "lon": 78.2}).json()
    assert ms[0]["distance_km"] <= ms[-1]["distance_km"]


def test_forecast_endpoint(client, db):
    cid = crop_id(db, "tomato")
    mid = db.scalar(select(Mandi.id).where(Mandi.code == "kolar"))
    r = client.get(f"{API}/forecasts", params={"crop_id": cid, "mandi_id": mid, "lang": "kn"})
    assert r.status_code == 200, r.text
    f = r.json()
    assert len(f["forecast"]) == 30
    assert all(p["lo"] <= p["yhat"] <= p["hi"] for p in f["forecast"])
    assert set(f["summary"]) == {"7", "14", "30"} and f["summary"]["7"]["mape"] is not None
    assert f["why"]["method"].startswith("TreeSHAP")
    assert f["history"] and f["last_price"] > 0


def test_recommend_hindi(client, db):
    h = login(client, "9000000003")
    r = client.post(f"{API}/recommend", headers=h, params={"lang": "hi"},
                    json={"crop_id": crop_id(db, "onion"), "quantity_qtl": 40})
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["best"]["net"] == max(o["net"] for o in rec["options"])
    assert rec["best"]["net"] >= rec["baseline"]["net"]
    assert any("ऀ" <= ch <= "ॿ" for ch in " ".join(rec["explanation"]))  # Devanagari


def test_end_to_end_marketplace(client, db):
    """Farmer posts a lot -> matched to a buyer demand -> both accept -> transaction + commission."""
    hf, hb, ha = login(client, FARMER), login(client, BUYER), login(client, ADMIN)
    tomato = crop_id(db, "tomato")
    rec = client.post(f"{API}/recommend", headers=hf, json={"crop_id": tomato, "quantity_qtl": 30}).json()
    ask = round(rec["baseline"]["price"] * 0.95)
    r = client.post(f"{API}/lots", headers=hf, json={"crop_id": tomato, "grade": "A", "quantity_qtl": 30, "ask_price": ask})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["matches"], "seeded tomato demand should match the new lot"
    m = body["matches"][0]
    assert ask < m["price_per_qtl"] and "phone" not in m["buyer"]  # contact hidden until accepted
    # The farmer is notified in-app
    assert any(a["kind"] == "match" for a in client.get(f"{API}/alerts", headers=hf).json())
    # Buyer sees it and both accept
    assert any(x["id"] == m["id"] for x in client.get(f"{API}/matches/mine", headers=hb).json())
    r = client.post(f"{API}/matches/{m['id']}/respond", headers=hf, json={"accept": True})
    assert r.json()["status"] == "proposed" and r.json()["farmer_accepted"]
    r = client.post(f"{API}/matches/{m['id']}/respond", headers=hb, json={"accept": True})
    assert r.json()["status"] == "accepted" and r.json()["farmer"]["phone"] == FARMER
    tx = client.get(f"{API}/transactions/mine", headers=hf).json()[0]
    assert tx["platform_revenue"] == round(tx["farmer_commission"] + tx["buyer_commission"], 2)
    assert tx["farmer_payout"] < tx["gross_amount"] < tx["buyer_total"]
    s = client.get(f"{API}/admin/summary", headers=ha).json()
    assert s["commission_earned"] >= tx["platform_revenue"] and s["transactions"] >= 1
    # Accepting again is a conflict
    assert client.post(f"{API}/matches/{m['id']}/respond", headers=hb, json={"accept": True}).status_code == 409


def test_reject_releases_quantity(client, db):
    hf = login(client, "9000000002")
    potato = crop_id(db, "potato")
    r = client.post(f"{API}/lots", headers=hf, json={"crop_id": potato, "grade": "A", "quantity_qtl": 10, "ask_price": 500})
    lot = r.json()["lot"]
    ms = r.json()["matches"]
    assert ms and lot["remaining_qtl"] < 10
    client.post(f"{API}/matches/{ms[0]['id']}/respond", headers=hf, json={"accept": False})
    mine = {x["id"]: x for x in client.get(f"{API}/lots/mine", headers=hf).json()}
    assert mine[lot["id"]]["remaining_qtl"] == lot["remaining_qtl"] + ms[0]["quantity_qtl"]


def test_buyer_demand_and_route(client, db):
    hb = login(client, "9100000004")
    r = client.post(f"{API}/demands", headers=hb, json={"crop_id": crop_id(db, "banana"), "quantity_qtl": 5, "max_price": 99999})
    assert r.status_code == 201
    route = client.get(f"{API}/buyer/route", headers=hb).json()
    assert route["solver"].startswith("OR-Tools") and len(route["stops"]) >= 1


def test_admin_views(client):
    ha = login(client, ADMIN)
    assert len(client.get(f"{API}/admin/users", headers=ha).json()) >= 10
    rep = client.get(f"{API}/admin/model-report", headers=ha).json()
    assert "MAPE" in rep["markdown"]
    runs = client.get(f"{API}/admin/ingestion-runs", headers=ha).json()
    assert runs and "rows_rejected" in runs[0]
    assert client.post(f"{API}/admin/jobs/match", headers=ha).status_code == 200


def test_profile_update_language(client):
    h = login(client, "9000000005")
    r = client.patch(f"{API}/me", headers=h, json={"language": "kn", "crop_ids": [1, 2, 999]})
    assert r.json()["language"] == "kn" and sorted(r.json()["farmer"]["crop_ids"]) == [1, 2]
