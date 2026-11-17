"""In-app alerts and the admin view (users, matches, commission, model + data health)."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Alert, Demand, IngestionRun, Lot, Match, ModelRun, PriceHistory, Transaction, User
from app.routers.market import match_out
from app.schemas import Lang
from app.security import current_user, require
from app.services.notify import render

alerts = APIRouter(tags=["alerts"])
admin = APIRouter(prefix="/admin", tags=["admin"])


@alerts.get("/alerts")
def list_alerts(lang: Lang | None = None, unread_only: bool = False, limit: int = Query(50, le=200),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Alert).where(Alert.user_id == user.id)
    if unread_only:
        q = q.where(Alert.is_read.is_(False))
    rows = db.scalars(q.order_by(Alert.id.desc()).limit(limit)).all()
    lg = lang or user.language
    return [{"id": a.id, "kind": a.kind, "severity": a.severity, "text": render(db, a, lg), "is_read": a.is_read,
             "channels": a.channels, "created_at": a.created_at.isoformat()} for a in rows]


@alerts.post("/alerts/{alert_id}/read")
def mark_read(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "alert not found")
    a.is_read = True
    db.commit()
    return {"ok": True}


@alerts.post("/alerts/read-all")
def mark_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(Alert.__table__.update().where(Alert.user_id == user.id).values(is_read=True))
    db.commit()
    return {"ok": True}


# ----- admin ----------------------------------------------------------------------------------
@admin.get("/summary")
def summary(_: User = Depends(require("admin")), db: Session = Depends(get_db)):
    users = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    ms = dict(db.execute(select(Match.status, func.count()).group_by(Match.status)).all())
    tx = db.execute(select(func.count(), func.coalesce(func.sum(Transaction.gross_amount), 0),
                           func.coalesce(func.sum(Transaction.platform_revenue), 0),
                           func.coalesce(func.sum(Transaction.quantity_qtl), 0))).one()
    run = db.scalar(select(ModelRun).where(ModelRun.is_active.is_(True)).order_by(ModelRun.id.desc()))
    return {
        "users": users, "matches": ms,
        "lots_open": db.scalar(select(func.count()).select_from(Lot).where(Lot.status.in_(("open", "partially_matched"))))
        , "demands_open": db.scalar(select(func.count()).select_from(Demand).where(Demand.status.in_(("open", "partially_matched")))),
        "transactions": tx[0], "gmv": round(tx[1], 2), "commission_earned": round(tx[2], 2), "volume_qtl": round(tx[3], 1),
        "commission_rates": {"farmer_pct": get_settings().farmer_commission_pct, "buyer_pct": get_settings().buyer_commission_pct},
        "price_rows": db.scalar(select(func.count()).select_from(PriceHistory)),
        "latest_price_date": (d.isoformat() if (d := db.scalar(select(func.max(PriceHistory.date)))) else None),
        "model": {"version": run.version, "best_model": run.best_model, "mape": run.metrics.get("mape_overall"),
                  "created_at": run.created_at.isoformat()} if run else None,
    }


@admin.get("/users")
def users(role: str | None = None, _: User = Depends(require("admin")), db: Session = Depends(get_db)):
    q = select(User).order_by(User.id)
    if role:
        q = q.where(User.role == role)
    return [{"id": u.id, "phone": u.phone, "name": u.name, "role": u.role, "language": u.language,
             "is_active": u.is_active, "created_at": u.created_at.isoformat(),
             "org": u.buyer.business_name if u.buyer else (u.farmer.village if u.farmer else "")} for u in db.scalars(q)]


@admin.get("/matches")
def matches(status: str | None = None, viewer: User = Depends(require("admin")), db: Session = Depends(get_db)):
    q = select(Match).order_by(Match.id.desc()).limit(200)
    if status:
        q = q.where(Match.status == status)
    return [match_out(m, viewer) for m in db.scalars(q)]


@admin.get("/transactions")
def transactions(_: User = Depends(require("admin")), db: Session = Depends(get_db)):
    return [{"id": t.id, "match_id": t.match_id, "crop": t.crop.name_en, "quantity_qtl": t.quantity_qtl,
             "price_per_qtl": t.price_per_qtl, "gross_amount": t.gross_amount, "platform_revenue": t.platform_revenue,
             "farmer_commission": t.farmer_commission, "buyer_commission": t.buyer_commission,
             "created_at": t.created_at.isoformat()} for t in db.scalars(select(Transaction).order_by(Transaction.id.desc()).limit(200))]


@admin.get("/model-report")
def model_report(_: User = Depends(require("admin"))):
    p = Path(get_settings().report_dir)
    js, md = p / "backtest_report.json", p / "backtest_report.md"
    if not js.exists():
        raise HTTPException(404, "no model report yet - run training")
    return {"report": json.loads(js.read_text()), "markdown": md.read_text() if md.exists() else ""}


@admin.get("/ingestion-runs")
def ingestion_runs(_: User = Depends(require("admin")), db: Session = Depends(get_db)):
    return [{"id": r.id, "source": r.source, "status": r.status, "started_at": r.started_at.isoformat(),
             "rows_in": r.rows_in, "rows_upserted": r.rows_upserted, "rows_rejected": r.rows_rejected,
             "rows_imputed": r.rows_imputed, "details": r.details}
            for r in db.scalars(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(30))]


@admin.post("/jobs/{job}")
def run_job(job: str, _: User = Depends(require("admin"))):
    from app import worker

    tasks = {"ingest": worker.ingest_task, "train": worker.train_task, "forecast": worker.forecast_task,
             "match": worker.match_task, "alerts": worker.alerts_task}
    if job not in tasks:
        raise HTTPException(404, f"unknown job; one of {sorted(tasks)}")
    r = tasks[job].delay()
    return {"queued": job, "task_id": r.id}
