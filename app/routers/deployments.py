import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.schemas.role import DeploymentCreate, CheckInOut, FeedbackCreate, QRAttendance
from app.database import get_supabase
from app.routers.auth import get_current_user, require_role
from app.services import fallback_data

router = APIRouter(prefix="/deployments", tags=["deployments"])

def _add_supervisor(db, deployment: dict) -> dict:
    """Attach contact details only for a volunteer already at the site."""
    deployment["supervisor"] = None
    if deployment.get("status") not in ("active", "completed") or not deployment.get("assigned_by"):
        return deployment
    staff = db.table("staff").select("id,name,phone,email").eq("id", deployment["assigned_by"]).execute()
    deployment["supervisor"] = staff.data[0] if staff.data else None
    return deployment

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
    try:
        db = get_supabase()
        result = db.table("deployments").select("*, roles(name, dept_name)").eq(
            "volunteer_id", user["sub"]
        ).order("scheduled_date", desc=True).execute()
        deployments = result.data or fallback_data.list_deployments(user["sub"])
    except Exception:
        deployments = fallback_data.list_deployments(user["sub"])

    try:
        for deployment in deployments:
            _add_supervisor(db, deployment)
    except Exception:
        pass

    return {"deployments": deployments}

@router.post("/{deployment_id}/qr-token")
def create_qr_token(deployment_id: str, user: dict = Depends(get_current_user)):
    """Create a short-lived QR ticket for the signed-in volunteer's own shift."""
    db = get_supabase()
    result = db.table("deployments").select("id,volunteer_id,status").eq("id", deployment_id).eq(
        "volunteer_id", user["sub"]
    ).execute()
    if not result.data or result.data[0]["status"] not in ("scheduled", "active"):
        raise HTTPException(404, "Active deployment not found")
    token = auth_service.create_access_token({
        "sub": user["sub"], "deployment_id": deployment_id, "purpose": "qr_attendance"
    }, expires_minutes=15)
    return {"token": token, "expires_in_minutes": 15}

def _qr_deployment(db, token: str) -> dict:
    payload = auth_service.decode_token(token)
    if not payload or payload.get("purpose") != "qr_attendance":
        raise HTTPException(401, "Invalid or expired QR code")
    result = db.table("deployments").select("*, roles(name, dept_name)").eq(
        "id", payload.get("deployment_id")
    ).eq("volunteer_id", payload.get("sub")).execute()
    if not result.data:
        raise HTTPException(404, "Deployment not found")
    return _add_supervisor(db, result.data[0])

@router.get("/qr/{token}")
def get_qr_deployment(token: str):
    """Resolve a short-lived QR ticket for the phone scan page."""
    return {"deployment": _qr_deployment(get_supabase(), token)}

@router.post("/qr-attendance")
def qr_attendance(body: QRAttendance):
    """Record QR arrival/departure without requiring a browser session on the phone."""
    if body.action not in ("checkin", "checkout"):
        raise HTTPException(400, "action must be 'checkin' or 'checkout'")
    db = get_supabase()
    deployment = _qr_deployment(db, body.token)
    if body.action == "checkin" and deployment["status"] != "scheduled":
        raise HTTPException(409, "This deployment cannot be checked in")
    if body.action == "checkout" and deployment["status"] != "active":
        raise HTTPException(409, "Check in before checking out")
    now = datetime.utcnow().isoformat()
    update = {"checked_in_at": now, "status": "active"} if body.action == "checkin" else {
        "checked_out_at": now, "status": "completed"
    }
    updated = db.table("deployments").update(update).eq("id", deployment["id"]).execute()
    return {"action": body.action, "timestamp": now, "deployment": _add_supervisor(db, updated.data[0])}

@router.post("/checkin")
def qr_checkin(body: CheckInOut, user: dict = Depends(get_current_user)):
    """QR check-in or check-out for a deployment."""
    if body.action not in ("checkin", "checkout"):
        raise HTTPException(400, "action must be 'checkin' or 'checkout'")
    db = get_supabase()
    dep = db.table("deployments").select("*").eq("id", body.deployment_id).eq(
        "volunteer_id", user["sub"]
    ).execute()
    if not dep.data:
        raise HTTPException(404, "Deployment not found for this volunteer")

    deployment = dep.data[0]
    if body.action == "checkin" and deployment["status"] != "scheduled":
        raise HTTPException(409, "This deployment cannot be checked in")
    if body.action == "checkout" and deployment["status"] != "active":
        raise HTTPException(409, "Check in before checking out")

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
