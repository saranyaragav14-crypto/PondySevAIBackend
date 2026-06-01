from fastapi import APIRouter, HTTPException, Depends
from app.database import get_supabase
from app.routers.auth import require_role

router = APIRouter(prefix="/roles", tags=["roles"])

@router.get("/")
def list_roles(dept_id: str | None = None, demand: str | None = None):
    """List all volunteer roles, optionally filtered."""
    db = get_supabase()
    query = db.table("roles").select("*")
    if dept_id:
        query = query.eq("dept_id", dept_id)
    if demand:
        query = query.eq("demand", demand)
    result = query.order("dept_id").execute()
    return {"roles": result.data}

@router.get("/departments")
def list_departments():
    """List all departments."""
    db = get_supabase()
    result = db.table("departments").select("*").execute()
    return {"departments": result.data}

@router.post("/")
def create_role(
    name: str, dept_id: str, qualifications: str,
    demand: str, description: str = "",
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Create a new volunteer role (nodal officer / admin only)."""
    db = get_supabase()
    import uuid
    role_id = str(uuid.uuid4())
    result = db.table("roles").insert({
        "id": role_id, "name": name, "dept_id": dept_id,
        "qualifications": qualifications, "demand": demand, "description": description,
    }).execute()
    return {"role": result.data[0]}
