"""Relational schema. price_history and weather become TimescaleDB hypertables on Postgres."""
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(10), index=True)  # farmer | buyer | admin
    language: Mapped[str] = mapped_column(String(5), default="en")  # en | hi | kn
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    farmer: Mapped["Farmer | None"] = relationship(back_populates="user", uselist=False)
    buyer: Mapped["Buyer | None"] = relationship(back_populates="user", uselist=False)


class Farmer(Base):
    __tablename__ = "farmers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    village: Mapped[str] = mapped_column(String(120), default="")
    district: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(80), default="Karnataka")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    land_acres: Mapped[float] = mapped_column(Float, default=0)
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="farmer")
    crops: Mapped[list["Crop"]] = relationship(secondary="farmer_crops")


class Buyer(Base):
    __tablename__ = "buyers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    business_name: Mapped[str] = mapped_column(String(160), default="")
    buyer_type: Mapped[str] = mapped_column(String(30), default="trader")  # trader|retailer|processor|exporter
    district: Mapped[str] = mapped_column(String(80), default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    user: Mapped[User] = relationship(back_populates="buyer")


class Crop(Base):
    __tablename__ = "crops"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name_en: Mapped[str] = mapped_column(String(60))
    name_hi: Mapped[str] = mapped_column(String(60))
    name_kn: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(30))  # vegetable|cereal|pulse|fibre|fruit|spice
    emoji: Mapped[str] = mapped_column(String(8), default="")
    agmarknet_name: Mapped[str] = mapped_column(String(60))
    perishability_k: Mapped[float] = mapped_column(Float)  # daily decay rate at 25°C
    storage_cost_per_qtl_day: Mapped[float] = mapped_column(Float, default=0.0)


class Msp(Base):
    __tablename__ = "msp"
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"), primary_key=True)
    season_year: Mapped[int] = mapped_column(Integer, primary_key=True)  # kharif marketing year start
    price: Mapped[float] = mapped_column(Float)
    is_estimate: Mapped[bool] = mapped_column(Boolean, default=False)


class FarmerCrop(Base):
    __tablename__ = "farmer_crops"
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"), primary_key=True)


class Mandi(Base):
    __tablename__ = "mandis"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    district: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(80), default="Karnataka")
    agmarknet_name: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    market_fee_pct: Mapped[float] = mapped_column(Float, default=1.0)
    commission_pct: Mapped[float] = mapped_column(Float, default=4.0)
    hamali_per_qtl: Mapped[float] = mapped_column(Float, default=20.0)


class PriceHistory(Base):
    """Daily mandi prices (Rs/quintal) and arrivals (tonnes). Hypertable on `date`."""

    __tablename__ = "price_history"
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"), primary_key=True)
    mandi_id: Mapped[int] = mapped_column(ForeignKey("mandis.id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    min_price: Mapped[float] = mapped_column(Float)
    max_price: Mapped[float] = mapped_column(Float)
    modal_price: Mapped[float] = mapped_column(Float)
    arrivals_tonnes: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="synthetic")
    is_imputed: Mapped[bool] = mapped_column(Boolean, default=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_price_mandi_date", "mandi_id", "date"),
        Index("ix_price_crop_date", "crop_id", "date"),
    )


class Weather(Base):
    """Daily weather per mandi. Hypertable on `date`. is_forecast marks Open-Meteo forecasts."""

    __tablename__ = "weather"
    mandi_id: Mapped[int] = mapped_column(ForeignKey("mandis.id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    temp_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_forecast: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="synthetic")


class CalendarEvent(Base):
    """Festival / seasonal calendar used as forecasting features."""

    __tablename__ = "calendar_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20), default="festival")  # festival|season
    demand_impact: Mapped[float] = mapped_column(Float, default=0.05)
    __table_args__ = (UniqueConstraint("date", "name", name="uq_event_date_name"),)


class Forecast(Base):
    __tablename__ = "forecasts"
    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    mandi_id: Mapped[int] = mapped_column(ForeignKey("mandis.id"))
    origin_date: Mapped[date] = mapped_column(Date)
    target_date: Mapped[date] = mapped_column(Date)
    horizon: Mapped[int] = mapped_column(Integer)
    yhat: Mapped[float] = mapped_column(Float)
    yhat_lo: Mapped[float] = mapped_column(Float)
    yhat_hi: Mapped[float] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String(30))
    model_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("crop_id", "mandi_id", "origin_date", "target_date", name="uq_forecast_point"),
        Index("ix_forecast_lookup", "crop_id", "mandi_id", "target_date"),
    )


class Lot(Base):
    __tablename__ = "lots"
    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), index=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    grade: Mapped[str] = mapped_column(String(1))  # A > B > C
    quantity_qtl: Mapped[float] = mapped_column(Float)
    remaining_qtl: Mapped[float] = mapped_column(Float)
    ask_price: Mapped[float] = mapped_column(Float)  # Rs/quintal at farm gate
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    available_from: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    crop: Mapped[Crop] = relationship()
    farmer: Mapped[Farmer] = relationship()
    __table_args__ = (Index("ix_lot_crop_status", "crop_id", "status"),)


class Demand(Base):
    __tablename__ = "demands"
    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id", ondelete="CASCADE"), index=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    min_grade: Mapped[str] = mapped_column(String(1))
    quantity_qtl: Mapped[float] = mapped_column(Float)
    remaining_qtl: Mapped[float] = mapped_column(Float)
    max_price: Mapped[float] = mapped_column(Float)  # Rs/quintal landed at buyer
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    max_distance_km: Mapped[float] = mapped_column(Float, default=150)
    needed_by: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    crop: Mapped[Crop] = relationship()
    buyer: Mapped[Buyer] = relationship()
    __table_args__ = (Index("ix_demand_crop_status", "crop_id", "status"),)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    demand_id: Mapped[int] = mapped_column(ForeignKey("demands.id", ondelete="CASCADE"), index=True)
    quantity_qtl: Mapped[float] = mapped_column(Float)
    price_per_qtl: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    transport_per_qtl: Mapped[float] = mapped_column(Float, default=0)
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)
    farmer_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    buyer_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    lot: Mapped[Lot] = relationship()
    demand: Mapped[Demand] = relationship()
    __table_args__ = (UniqueConstraint("lot_id", "demand_id", name="uq_match_pair"),)


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), unique=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"), index=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id"))
    quantity_qtl: Mapped[float] = mapped_column(Float)
    price_per_qtl: Mapped[float] = mapped_column(Float)
    gross_amount: Mapped[float] = mapped_column(Float)
    farmer_commission: Mapped[float] = mapped_column(Float)
    buyer_commission: Mapped[float] = mapped_column(Float)
    platform_revenue: Mapped[float] = mapped_column(Float)
    farmer_payout: Mapped[float] = mapped_column(Float)
    buyer_total: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")  # confirmed|settled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    crop: Mapped[Crop] = relationship()


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    crop_id: Mapped[int | None] = mapped_column(ForeignKey("crops.id"), nullable=True)
    mandi_id: Mapped[int | None] = mapped_column(ForeignKey("mandis.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))  # price_rise|price_drop|forecast_rise|forecast_drop|match
    severity: Mapped[str] = mapped_column(String(10), default="info")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    channels: Mapped[list] = mapped_column(JSON, default=list)
    dedup_key: Mapped[str] = mapped_column(String(160), unique=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    rows_in: Mapped[int] = mapped_column(Integer, default=0)
    rows_upserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    rows_imputed: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[str] = mapped_column(String(40), unique=True)
    best_model: Mapped[str] = mapped_column(String(30))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    report_path: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
