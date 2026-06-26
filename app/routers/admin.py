from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_supabase
from app.routers.auth import require_role
from app.services import auth as auth_service
import bcrypt
import uuid

router = APIRouter(prefix="/admin", tags=["admin"])
_fallback_created_staff: dict[str, dict] = {}


class CreateStaffRequest(BaseModel):
    name: str
    email: str
    password: str
    commune: str
    role: str = "nodal_officer"


@router.post("/staff")
def create_staff(
    body: CreateStaffRequest,
    user: dict = Depends(require_role("admin")),
):
    """Admin only: Create a new nodal officer or admin account."""
    if body.role not in ("nodal_officer", "admin"):
        raise HTTPException(400, "Role must be 'nodal_officer' or 'admin'")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    staff_record = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "email": body.email.strip().lower(),
        "password_hash": password_hash,
        "role": body.role,
        "commune": body.commune,
    }

    try:
        db = get_supabase()
        existing = db.table("staff").select("id").eq("email", staff_record["email"]).execute()
        if existing.data:
            raise HTTPException(409, "A staff account with this email already exists")
        result = db.table("staff").insert(staff_record).execute()
        if not result.data:
            raise HTTPException(500, "Failed to create staff account")
        created = result.data[0]
    except HTTPException:
        raise
    except Exception:
        if any(staff["email"] == staff_record["email"] for staff in auth_service.list_fallback_staff()):
            raise HTTPException(409, "A staff account with this email already exists")
        _fallback_created_staff[staff_record["id"]] = {
            **staff_record,
            "created_at": None,
        }
        created = _fallback_created_staff[staff_record["id"]]

    return {
        "created": True,
        "id": created["id"],
        "name": created["name"],
        "email": created["email"],
        "role": created["role"],
        "commune": created["commune"],
    }


@router.get("/staff")
def list_staff(user: dict = Depends(require_role("admin"))):
    """Admin only: List all staff accounts."""
    try:
        db = get_supabase()
        result = db.table("staff").select(
            "id,name,email,role,commune,created_at"
        ).order("created_at", desc=True).execute()
        staff = result.data or []
    except Exception:
        staff = []

    by_email = {member["email"]: member for member in staff}
    for member in auth_service.list_fallback_staff() + list(_fallback_created_staff.values()):
        by_email.setdefault(member["email"], {
            "id": member["id"],
            "name": member["name"],
            "email": member["email"],
            "role": member["role"],
            "commune": member.get("commune") or "Puducherry",
            "created_at": member.get("created_at"),
        })
    return {"staff": list(by_email.values())}


@router.delete("/staff/{staff_id}")
def delete_staff(staff_id: str, user: dict = Depends(require_role("admin"))):
    """Admin only: Remove a staff account."""
    if staff_id == user.get("sub"):
        raise HTTPException(400, "You cannot delete your own account")
    if staff_id in _fallback_created_staff:
        del _fallback_created_staff[staff_id]
        return {"deleted": True}
    if staff_id in {staff["id"] for staff in auth_service.list_fallback_staff()}:
        raise HTTPException(400, "Built-in fallback staff accounts cannot be deleted")
    try:
        db = get_supabase()
        result = db.table("staff").delete().eq("id", staff_id).execute()
        if not result.data:
            raise HTTPException(404, "Staff account not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "Staff database is unavailable") from exc
    return {"deleted": True}
