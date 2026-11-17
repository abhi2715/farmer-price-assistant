from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Buyer, Crop, Farmer, FarmerCrop, User
from app.ratelimit import limiter
from app.schemas import MeUpdate, OtpRequest, OtpVerify
from app.security import create_token, current_user, issue_otp, verify_otp

router = APIRouter(tags=["auth"])
DEFAULT_LOC = (12.9716, 77.5946)  # Bengaluru, used until the user shares location


def user_out(u: User) -> dict:
    d = {"id": u.id, "phone": u.phone, "name": u.name, "role": u.role, "language": u.language}
    if u.farmer:
        f = u.farmer
        d["farmer"] = {"id": f.id, "village": f.village, "district": f.district, "lat": f.lat, "lon": f.lon,
                       "sms_opt_in": f.sms_opt_in, "whatsapp_opt_in": f.whatsapp_opt_in,
                       "crop_ids": [c.id for c in f.crops]}
    if u.buyer:
        b = u.buyer
        d["buyer"] = {"id": b.id, "business_name": b.business_name, "buyer_type": b.buyer_type, "lat": b.lat, "lon": b.lon}
    return d


@router.post("/auth/otp/request")
@limiter.limit(lambda: get_settings().rate_limit_otp)
def otp_request(request: Request, body: OtpRequest):
    otp = issue_otp(body.phone)
    # Real deployments send the OTP via the SMS channel; dev mode returns it for the demo.
    out = {"sent": True, "expires_in": get_settings().otp_ttl_seconds}
    if get_settings().otp_dev_mode:
        out["dev_otp"] = otp
    return out


@router.post("/auth/otp/verify")
@limiter.limit("20/minute")
def otp_verify(request: Request, body: OtpVerify, db: Session = Depends(get_db)):
    if not verify_otp(body.phone, body.otp):
        raise HTTPException(401, "invalid or expired OTP")
    user = db.scalar(select(User).where(User.phone == body.phone))
    created = False
    if user is None:
        lat, lon = (body.lat, body.lon) if body.lat is not None and body.lon is not None else DEFAULT_LOC
        user = User(phone=body.phone, name=body.name, role=body.role, language=body.language)
        db.add(user)
        db.flush()
        if body.role == "farmer":
            db.add(Farmer(user_id=user.id, lat=lat, lon=lon))
        else:
            db.add(Buyer(user_id=user.id, business_name=body.business_name or body.name, lat=lat, lon=lon))
        db.commit()
        db.refresh(user)
        created = True
    if not user.is_active:
        raise HTTPException(403, "account disabled")
    return {"access_token": create_token(user), "token_type": "bearer", "user": user_out(user), "created": created}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(body: MeUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None:
        user.name = body.name
    if body.language is not None:
        user.language = body.language
    prof = user.farmer or user.buyer
    if prof is not None and body.lat is not None and body.lon is not None:
        prof.lat, prof.lon = body.lat, body.lon
    if user.farmer:
        f = user.farmer
        for k in ("village", "sms_opt_in", "whatsapp_opt_in"):
            v = getattr(body, k)
            if v is not None:
                setattr(f, k, v)
        if body.crop_ids is not None:
            valid = set(db.scalars(select(Crop.id).where(Crop.id.in_(body.crop_ids))))
            db.execute(delete(FarmerCrop).where(FarmerCrop.farmer_id == f.id))
            db.add_all([FarmerCrop(farmer_id=f.id, crop_id=c) for c in valid])
    db.commit()
    db.refresh(user)
    return user_out(user)
