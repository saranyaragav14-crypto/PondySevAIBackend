from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.schemas.auth import OTPRequest, OTPVerify, TokenOut, NodalOfficerLogin, AdminLogin
from app.services import auth as auth_service
from app.config import get_settings
import bcrypt

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()
settings = get_settings()

@router.post("/otp/send")
def send_otp(body: OTPRequest):
    """Send OTP to volunteer phone number."""
    import re
    digits = re.sub(r'\D', '', body.phone)
    if len(digits) != 10:
        raise HTTPException(400, "Phone must be 10 digits")
    try:
        result = auth_service.send_otp(digits)
    except auth_service.OtpServiceUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return result

@router.post("/otp/verify", response_model=TokenOut)
def verify_otp(body: OTPVerify):
    """Verify OTP and issue JWT for volunteer."""
    import re
    digits = re.sub(r'\D', '', body.phone)
    try:
        valid = auth_service.verify_otp(digits, body.otp)
    except auth_service.OtpServiceUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    if not valid:
        raise HTTPException(401, "Invalid or expired OTP")

    try:
        volunteer = auth_service.get_volunteer_by_phone(digits)
    except auth_service.VolunteerLookupUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    if not volunteer:
        raise HTTPException(404, "No registered volunteer found for this phone number")

    token = auth_service.create_access_token({
        "sub": volunteer["id"],
        "role": "volunteer",
        "name": volunteer["full_name"],
        "phone": digits,
    })
    return TokenOut(access_token=token, role="volunteer", name=volunteer["full_name"])

@router.post("/staff/login", response_model=TokenOut)
def staff_login(body: NodalOfficerLogin):
    """Nodal officer email/password login."""
    from app.database import get_supabase
    db = get_supabase()
    email = body.email.strip().lower()
    result = db.table("staff").select("*").eq("email", email).eq("role", "nodal_officer").execute()
    if not result.data:
        raise HTTPException(401, "Invalid credentials")
    staff = result.data[0]
    if not bcrypt.checkpw(body.password.encode(), staff["password_hash"].encode()):
        raise HTTPException(401, "Invalid credentials")
    token = auth_service.create_access_token({"sub": staff["id"], "role": "nodal_officer", "name": staff["name"]})
    return TokenOut(access_token=token, role="nodal_officer", name=staff["name"])

@router.post("/admin/login", response_model=TokenOut)
def admin_login(body: AdminLogin):
    """Admin email/password login."""
    from app.database import get_supabase
    db = get_supabase()
    email = body.email.strip().lower()
    result = db.table("staff").select("*").eq("email", email).eq("role", "admin").execute()
    if not result.data:
        raise HTTPException(401, "Invalid credentials")
    staff = result.data[0]
    if not bcrypt.checkpw(body.password.encode(), staff["password_hash"].encode()):
        raise HTTPException(401, "Invalid credentials")
    token = auth_service.create_access_token({"sub": staff["id"], "role": "admin", "name": staff["name"]})
    return TokenOut(access_token=token, role="admin", name=staff["name"])

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = auth_service.decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    return payload

def require_role(*roles: str):
    def dependency(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(403, f"Requires role: {roles}")
        return user
    return dependency
