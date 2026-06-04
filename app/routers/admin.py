from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_supabase
from app.routers.auth import require_role
import bcrypt
import uuid

router = APIRouter(prefix="/admin", tags=["admin"])


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

    db = get_supabase()
    existing = db.table("staff").select("id").eq("email", body.email).execute()
    if existing.data:
        raise HTTPException(409, "A staff account with this email already exists")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    result = db.table("staff").insert({
        "id": str(uuid.uuid4()),
        "name": body.name,
        "email": body.email,
        "password_hash": password_hash,
        "role": body.role,
        "commune": body.commune,
    }).execute()

    if not result.data:
        raise HTTPException(500, "Failed to create staff account")

    created = result.data[0]
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
    db = get_supabase()
    result = db.table("staff").select(
        "id,name,email,role,commune,created_at"
    ).order("created_at", desc=True).execute()
    return {"staff": result.data}


@router.delete("/staff/{staff_id}")
def delete_staff(staff_id: str, user: dict = Depends(require_role("admin"))):
    """Admin only: Remove a staff account."""
    if staff_id == user.get("sub"):
        raise HTTPException(400, "You cannot delete your own account")
    db = get_supabase()
    result = db.table("staff").delete().eq("id", staff_id).execute()
    if not result.data:
        raise HTTPException(404, "Staff account not found")
    return {"deleted": True}