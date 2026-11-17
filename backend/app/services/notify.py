"""Alerts: generation from price moves/forecasts, plus pluggable SMS / WhatsApp delivery.

Delivery is mocked locally (logged + appended to an outbox file). Set SMS_WEBHOOK_URL /
WHATSAPP_WEBHOOK_URL to POST {to, text} to a real provider bridge (Twilio, Gupshup, MSG91...).
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import ROOT, get_settings
from app.i18n import t
from app.models import Alert, Crop, Farmer, FarmerCrop, Forecast, Mandi, PriceHistory, User
from app.services.logistics import road_km

log = logging.getLogger("agriroute.notify")
OUTBOX = ROOT / "notifications_outbox.jsonl"
FORECAST_MOVE_PCT = 8.0
DAILY_MOVE_PCT = 10.0
WATCH_RADIUS_KM = 150


class Channel:
    name = "base"

    def send(self, phone: str, text: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


class WebhookOrMockChannel(Channel):
    def __init__(self, name: str, url: str):
        self.name, self.url = name, url

    def send(self, phone: str, text: str) -> bool:
        if self.url:
            try:
                httpx.post(self.url, json={"to": f"+91{phone}", "text": text, "channel": self.name}, timeout=5).raise_for_status()
                return True
            except Exception as e:
                log.warning("%s delivery failed: %s", self.name, e)
                return False
        log.info("[mock %s] to +91%s: %s", self.name, phone, text)
        try:
            with Path(OUTBOX).open("a", encoding="utf-8") as f:
                f.write(json.dumps({"channel": self.name, "to": phone, "text": text}, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return True


def channels() -> dict[str, Channel]:
    s = get_settings()
    return {"sms": WebhookOrMockChannel("sms", s.sms_webhook_url),
            "whatsapp": WebhookOrMockChannel("whatsapp", s.whatsapp_webhook_url)}


def render(db: Session, alert: Alert, lang: str) -> str:
    p = dict(alert.params or {})
    if alert.crop_id:
        c = db.get(Crop, alert.crop_id)
        p["crop"] = getattr(c, f"name_{lang}", c.name_en)
    if alert.mandi_id:
        p["mandi"] = db.get(Mandi, alert.mandi_id).name
    return t(f"alert.{alert.kind}", lang, **p)


def create_alert(db: Session, user: User, kind: str, dedup_key: str, crop_id=None, mandi_id=None,
                 params: dict | None = None, severity: str = "info", push: bool = True) -> Alert | None:
    """Insert an in-app alert (idempotent via dedup_key) and fan out to opted-in channels."""
    if db.scalar(select(Alert.id).where(Alert.dedup_key == dedup_key)):
        return None
    a = Alert(user_id=user.id, kind=kind, crop_id=crop_id, mandi_id=mandi_id, params=params or {},
              severity=severity, dedup_key=dedup_key, channels=["in_app"])
    try:
        with db.begin_nested():
            db.add(a)
            db.flush()
    except IntegrityError:
        return None
    if push:
        sent = ["in_app"]
        f = user.farmer
        chans = channels()
        text = render(db, a, user.language)
        if f is None or f.sms_opt_in:
            if chans["sms"].send(user.phone, text):
                sent.append("sms")
        if f is not None and f.whatsapp_opt_in and chans["whatsapp"].send(user.phone, text):
            sent.append("whatsapp")
        a.channels = sent
    return a


def generate_price_alerts(db: Session, today: date | None = None) -> int:
    """Per farmer x watched crop x nearby mandi: daily moves and forecast moves beyond thresholds."""
    last = db.scalar(select(func.max(PriceHistory.date)))
    if last is None:
        return 0
    n = 0
    mandis = db.scalars(select(Mandi)).all()
    fc_origin = db.scalar(select(func.max(Forecast.origin_date)))
    for farmer in db.scalars(select(Farmer)):
        user = farmer.user
        if not user.is_active:
            continue
        near = [m for m in mandis if road_km(farmer.lat, farmer.lon, m.lat, m.lon) <= WATCH_RADIUS_KM]
        crop_ids = [c for (c,) in db.execute(select(FarmerCrop.crop_id).where(FarmerCrop.farmer_id == farmer.id)).all()]
        for cid in crop_ids:
            top = None  # biggest forecast move among nearby mandis -> at most one forecast alert per crop
            for m in near:
                rows = db.execute(select(PriceHistory.date, PriceHistory.modal_price)
                                  .where(PriceHistory.crop_id == cid, PriceHistory.mandi_id == m.id,
                                         PriceHistory.date >= last - timedelta(days=1), PriceHistory.is_imputed.is_(False))
                                  .order_by(PriceHistory.date)).all()
                if len(rows) == 2:
                    chg = (rows[1][1] / rows[0][1] - 1) * 100
                    if abs(chg) >= DAILY_MOVE_PCT:
                        kind = "price_rise" if chg > 0 else "price_drop"
                        if create_alert(db, user, kind, f"{kind}:{user.id}:{cid}:{m.id}:{last}", cid, m.id,
                                        {"pct": round(abs(chg), 1), "price": round(rows[1][1])}, "warning"):
                            n += 1
                if fc_origin:
                    f7 = db.scalar(select(Forecast).where(Forecast.crop_id == cid, Forecast.mandi_id == m.id,
                                                          Forecast.origin_date == fc_origin, Forecast.horizon == 7))
                    cur = db.scalar(select(PriceHistory.modal_price).where(
                        PriceHistory.crop_id == cid, PriceHistory.mandi_id == m.id, PriceHistory.date == fc_origin))
                    if f7 and cur:
                        chg = (f7.yhat / cur - 1) * 100
                        if abs(chg) >= FORECAST_MOVE_PCT and (top is None or abs(chg) > abs(top[0])):
                            top = (chg, m.id, cur, f7.yhat)
            if top:
                chg, mid, cur, fut = top
                kind = "forecast_rise" if chg > 0 else "forecast_drop"
                if create_alert(db, user, kind, f"{kind}:{user.id}:{cid}:{fc_origin}", cid, mid,
                                {"pct": round(abs(chg), 1), "days": 7, "p0": round(cur), "p1": round(fut)},
                                "info" if chg > 0 else "warning"):
                    n += 1
    db.commit()
    return n
