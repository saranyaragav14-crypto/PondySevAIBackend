"""
Auth service — OTP generation and verification.
JWT issued by this backend after verification.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional

import httpx
from jose import jwt, JWTError
from redis import Redis
from redis.exceptions import RedisError
from app.config import get_settings
from app.database import get_supabase

settings = get_settings()

_otp_store: dict[str, tuple[str, datetime]] = {}
_redis_client: Redis | None = None

FALLBACK_STAFF = {
    ("officer@puducherry.gov.in", "nodal_officer"): {
        "id": "fallback-nodal-officer",
        "name": "Nodal Officer",
        "password": "Officer@123",
    },
    ("admin@pondysevai.in", "admin"): {
        "id": "fallback-admin",
        "name": "Admin",
        "password": "Admin@123",
    },
}


class OtpServiceUnavailable(RuntimeError):
    """Raised when production OTP storage or delivery is unavailable."""


class VolunteerLookupUnavailable(RuntimeError):
    """Raised when the volunteer database cannot be queried during sign-in."""


class StaffLookupUnavailable(RuntimeError):
    """Raised when the staff database cannot be queried during sign-in."""


def _is_production() -> bool:
    return settings.app_env.lower() == "production"


def _get_redis() -> Redis | None:
    global _redis_client
    if not settings.redis_url:
        return None
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        _redis_client.ping()
    except RedisError as exc:
        if _is_production():
            raise OtpServiceUnavailable("OTP storage is unavailable") from exc
        return None
    return _redis_client


def _otp_key(phone: str) -> str:
    return f"pondysevai:otp:{phone}"

def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"

def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or settings.jwt_expire_minutes
    )
    return jwt.encode(
        {**data, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None

def send_otp(phone: str) -> dict:
    """
    Generate OTP and attempt to send via SMS.
    Always returns dev_otp so testing works even without Twilio.
    """
    otp = _generate_otp()
    redis = _get_redis()
    if redis:
        try:
            redis.set(_otp_key(phone), otp, ex=settings.otp_ttl_seconds)
        except RedisError as exc:
            if _is_production():
                raise OtpServiceUnavailable("OTP storage is unavailable") from exc
            _otp_store[phone] = (otp, datetime.utcnow() + timedelta(seconds=settings.otp_ttl_seconds))
    elif _is_production():
        raise OtpServiceUnavailable("OTP storage is not configured")
    else:
        _otp_store[phone] = (otp, datetime.utcnow() + timedelta(seconds=settings.otp_ttl_seconds))

    # Try to send via Twilio if configured
    if settings.twilio_account_sid:
        try:
            _send_twilio_sms(phone, otp)
            return {"sent": True, "method": "twilio"}
        except Exception as e:
            print(f"[OTP] Twilio failed: {e} — returning dev_otp")

    if _is_production():
        raise OtpServiceUnavailable("SMS delivery is not configured")

    # Demo OTP is intentionally limited to non-production environments.
    return {"sent": True, "method": "dev", "dev_otp": otp}

def _send_twilio_sms(phone: str, otp: str):
    from twilio.rest import Client as TwilioClient
    client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
    client.messages.create(
        body=f"Your PondySevAi OTP is: {otp}. Valid for 10 minutes.",
        from_=settings.twilio_from_number,
        to=f"+91{phone}",
    )

def verify_otp(phone: str, otp: str) -> bool:
    redis = _get_redis()
    if redis:
        try:
            stored = redis.get(_otp_key(phone))
            if stored != otp:
                return False
            redis.delete(_otp_key(phone))
            return True
        except RedisError as exc:
            if _is_production():
                raise OtpServiceUnavailable("OTP storage is unavailable") from exc
            return False
    if _is_production():
        raise OtpServiceUnavailable("OTP storage is not configured")

    record = _otp_store.get(phone)
    if not record:
        return False
    stored, expires_at = record
    if expires_at <= datetime.utcnow():
        del _otp_store[phone]
        return False
    if stored != otp:
        return False
    del _otp_store[phone]
    return True

def get_volunteer_by_phone(phone: str) -> Optional[dict]:
    try:
        db = get_supabase()
        result = db.table("volunteers").select("*").eq("phone", phone).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        raise VolunteerLookupUnavailable("Volunteer database is unavailable") from exc

def get_staff_by_email(email: str, role: str) -> Optional[dict]:
    if not settings.supabase_url or not settings.supabase_server_key:
        raise StaffLookupUnavailable("Staff database is not configured")

    url = f"{settings.supabase_url.rstrip('/')}/rest/v1/staff"
    headers = {
        "apikey": settings.supabase_server_key,
        "Authorization": f"Bearer {settings.supabase_server_key}",
    }
    params = {
        "select": "*",
        "email": f"eq.{email}",
        "role": f"eq.{role}",
        "limit": "1",
    }

    try:
        response = httpx.get(url, headers=headers, params=params, timeout=8)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise StaffLookupUnavailable("Staff database is unavailable") from exc

    data = response.json()
    return data[0] if data else None

def get_fallback_staff(email: str, role: str, password: str) -> Optional[dict]:
    staff = FALLBACK_STAFF.get((email, role))
    if not staff or not secrets.compare_digest(password, staff["password"]):
        return None
    return {
        "id": staff["id"],
        "name": staff["name"],
        "role": role,
    }
