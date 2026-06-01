import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.schemas.role import DeploymentCreate, CheckInOut, FeedbackCreate
from app.database import get_supabase
from app.routers.auth import get_current_user, require_role

router = APIRouter(prefix="/deployments", tags=["deployments"])

@router.post("/", status_code=201)
def create_deployment(
    body: DeploymentCreate,
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Create a deployment (assign volunteer to a shift)."""
    db = get_supabase()
    dep_id = str(uuid.uuid4())
    result = db.table("deployments").insert({
        "id": dep_id,
        "volunteer_id": body.volunteer_id,
        "role_id": body.role_id,
        "location": body.location,
        "scheduled_date": body.scheduled_date,
        "shift": body.shift,
        "status": "scheduled",
    }).execute()
    return {"deployment": result.data[0]}

@router.get("/my")
def my_deployments(user: dict = Depends(get_current_user)):
    """Get all deployments for the logged-in volunteer."""
    db = get_supabase()
    result = db.table("deployments").select("*, roles(name, dept_name)").eq(
        "volunteer_id", user["sub"]
    ).order("scheduled_date", desc=True).execute()
    return {"deployments": result.data}

@router.post("/checkin")
def qr_checkin(body: CheckInOut, user: dict = Depends(get_current_user)):
    """QR check-in or check-out for a deployment."""
    if body.action not in ("checkin", "checkout"):
        raise HTTPException(400, "action must be 'checkin' or 'checkout'")
    db = get_supabase()
    dep = db.table("deployments").select("*").eq("id", body.deployment_id).execute()
    if not dep.data:
        raise HTTPException(404, "Deployment not found")

    update = {}
    if body.action == "checkin":
        update = {"checked_in_at": datetime.utcnow().isoformat(), "status": "active"}
    else:
        update = {"checked_out_at": datetime.utcnow().isoformat(), "status": "completed"}

    db.table("deployments").update(update).eq("id", body.deployment_id).execute()
    return {"action": body.action, "timestamp": datetime.utcnow().isoformat()}

@router.post("/feedback")
def submit_feedback(
    body: FeedbackCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Submit feedback for a volunteer after deployment."""
    if body.category not in ("top_performer", "performer", "regular"):
        raise HTTPException(400, "Invalid feedback category")
    db = get_supabase()
    import uuid
    db.table("feedback").insert({
        "id": str(uuid.uuid4()),
        "volunteer_id": body.volunteer_id,
        "deployment_id": body.deployment_id,
        "category": body.category,
        "notes": body.notes,
        "submitted_by": user["sub"],
    }).execute()

    # Update volunteer's latest feedback on their profile
    db.table("volunteers").update({"latest_feedback": body.category}).eq(
        "id", body.volunteer_id
    ).execute()

    # Check if tier upgrade is needed
    background_tasks.add_task(_check_tier_upgrade, body.volunteer_id)
    return {"feedback": "recorded"}

def _check_tier_upgrade(volunteer_id: str):
    """Calculate completed deployment months and upgrade tier if threshold met."""
    db = get_supabase()
    completed = db.table("deployments").select("scheduled_date").eq(
        "volunteer_id", volunteer_id
    ).eq("status", "completed").execute()

    months = len(set(d["scheduled_date"][:7] for d in completed.data))  # unique YYYY-MM

    if months >= 12:
        new_tier = "platinum"
    elif months >= 6:
        new_tier = "gold"
    elif months >= 3:
        new_tier = "silver"
    elif months >= 1:
        new_tier = "bronze"
    else:
        return

    db.table("volunteers").update({"tier": new_tier}).eq("id", volunteer_id).execute()
