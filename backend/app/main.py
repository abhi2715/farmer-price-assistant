import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal
from app.ratelimit import limiter
from app.routers import alerts_admin, auth, insights, market

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("agriroute")


def _bootstrap_loop(interval_h: float) -> None:
    """Idempotent seed/ingest/forecast/match/alerts, then repeat. Replaces Celery beat on single-process hosts."""
    from app.scripts import bootstrap

    while True:
        try:
            bootstrap.main()
        except Exception:
            log.exception("background bootstrap failed; retrying next cycle")
        time.sleep(interval_h * 3600)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    s = get_settings()
    if s.bootstrap_on_startup:
        threading.Thread(target=_bootstrap_loop, args=(s.bootstrap_interval_hours,), daemon=True, name="bootstrap").start()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="AgriRoute API", version="1.0.0",
                  description="Farm-to-market optimizer: forecasts, sell decisions and a buyer marketplace.",
                  lifespan=_lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=800)  # low-bandwidth friendly
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
                       allow_origin_regex=s.cors_origin_regex or None, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errs = [{"field": ".".join(str(p) for p in e["loc"][1:]), "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "validation error", "errors": errs})

    api = "/api/v1"
    for r in (auth.router, insights.router, market.router, alerts_admin.alerts, alerts_admin.admin):
        app.include_router(r, prefix=api)

    @app.get("/health")
    @limiter.exempt
    def health():
        db = SessionLocal()
        try:
            db.execute(text("select 1"))
            ok = True
        except Exception:
            ok = False
        finally:
            db.close()
        from app.services.forecasting import active_model

        m = active_model()
        return {"status": "ok" if ok else "degraded", "db": ok, "model": m.version if m else None}

    return app


app = create_app()
