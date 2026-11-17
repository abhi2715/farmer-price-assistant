from datetime import date, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Phone = Field(pattern=r"^[6-9]\d{9}$", description="10-digit Indian mobile number")
Lang = Literal["en", "hi", "kn"]
Grade = Literal["A", "B", "C"]
Lat = Annotated[float | None, Field(ge=6.0, le=37.5)]  # India bounding box
Lon = Annotated[float | None, Field(ge=68.0, le=97.5)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OtpRequest(Strict):
    phone: str = Phone


class OtpVerify(Strict):
    phone: str = Phone
    otp: str = Field(pattern=r"^\d{6}$")
    # Only used on first login (sign-up). Admins cannot self-register.
    role: Literal["farmer", "buyer"] = "farmer"
    name: str = Field("", max_length=120)
    language: Lang = "en"
    lat: Lat = None
    lon: Lon = None
    business_name: str = Field("", max_length=160)


class MeUpdate(Strict):
    name: str | None = Field(None, max_length=120)
    language: Lang | None = None
    lat: Lat = None
    lon: Lon = None
    village: str | None = Field(None, max_length=120)
    crop_ids: list[int] | None = Field(None, max_length=20)
    sms_opt_in: bool | None = None
    whatsapp_opt_in: bool | None = None


class RecommendIn(Strict):
    crop_id: int = Field(gt=0)
    quantity_qtl: float = Field(gt=0, le=10000)
    lat: Lat = None
    lon: Lon = None
    max_wait_days: int = Field(14, ge=0, le=30)


class LotIn(Strict):
    crop_id: int = Field(gt=0)
    grade: Grade = "B"
    quantity_qtl: float = Field(gt=0, le=10000)
    ask_price: float = Field(gt=0, le=200000, description="Rs per quintal at farm gate")
    lat: Lat = None
    lon: Lon = None
    available_from: date | None = None

    @field_validator("available_from")
    @classmethod
    def not_past(cls, v):
        if v and v < date.today() - timedelta(days=1):
            raise ValueError("available_from cannot be in the past")
        return v


class DemandIn(Strict):
    crop_id: int = Field(gt=0)
    min_grade: Grade = "B"
    quantity_qtl: float = Field(gt=0, le=100000)
    max_price: float = Field(gt=0, le=200000, description="Rs per quintal landed at buyer")
    max_distance_km: float = Field(150, gt=0, le=1500)
    needed_by: date | None = None
    lat: Lat = None
    lon: Lon = None

    @model_validator(mode="after")
    def default_date(self):
        if self.needed_by is None:
            self.needed_by = date.today() + timedelta(days=14)
        elif self.needed_by < date.today():
            raise ValueError("needed_by cannot be in the past")
        return self


class MatchAction(Strict):
    accept: bool
