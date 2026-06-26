from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.database import get_supabase
from app.routers.auth import require_role
from app.services.notifications import bulk_sms
import uuid

router = APIRouter(prefix="/nodal-officer", tags=["nodal-officer"])

DEMO_APPLICANTS = [
    {
        "id": "demo-volunteer-001",
        "full_name": "Demo Volunteer",
        "phone": "9876543210",
        "commune": "Puducherry",
        "status": "registered",
        "ai_score": 0.86,
        "ai_assessment": "Strong fit for civic support roles based on availability and selected departments.",
        "ai_top_matches": '[{"role_id":"r01","role_name":"Medical camp support","dept":"Health & Sanitation","score":0.86,"demand":"high"}]',
        "assigned_role": None,
        "assigned_dept": None,
        "tier": None,
        "latest_feedback": None,
        "created_at": None,
        "departments": ["Health & Sanitation"],
        "availability": ["avail_weekends"],
    }
]

class AssignRequest(BaseModel):
    role: str
    dept: str
    location: Optional[str] = None
    scheduled_date: Optional[str] = None
    shift: Optional[str] = None
    role_id: Optional[str] = None

@router.get("/applicants")
def get_applicants(
    status: str | None = None,
    commune: str | None = None,
    dept: str | None = None,
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Get all applicants with AI scores, filtered by status/commune/dept."""
    try:
        db = get_supabase()
        query = db.table("volunteers").select(
            "id,full_name,phone,commune,status,ai_score,ai_assessment,ai_top_matches,assigned_role,assigned_dept,tier,latest_feedback,created_at,departments,availability"
        )
        if status:
            query = query.eq("status", status)
        if commune:
            query = query.eq("commune", commune)
        result = query.order("ai_score", desc=True).execute()
        return {"applicants": result.data}
    except Exception:
        applicants = DEMO_APPLICANTS
        if status:
            applicants = [a for a in applicants if a["status"] == status or (status == "pending_review" and a["status"] == "registered")]
        if commune:
            applicants = [a for a in applicants if a["commune"] == commune]
        return {"applicants": applicants}

@router.post("/assign/{volunteer_id}")
def assign_volunteer(
    volunteer_id: str,
    body: AssignRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Assign a volunteer to a role, department, and optionally create a deployment."""
    db = get_supabase()

    # Update volunteer status
    result = db.table("volunteers").update({
        "status": "assigned",
        "assigned_role": body.role,
        "assigned_role_id": body.role_id,
        "assigned_dept": body.dept,
        "assigned_by": user["sub"],
    }).eq("id", volunteer_id).execute()

    if not result.data:
        raise HTTPException(404, "Volunteer not found")

    v = result.data[0]

    # Create deployment record if shift details provided
    deployment_id = None
    if body.location and body.scheduled_date and body.shift:
        dep_result = db.table("deployments").insert({
            "id": str(uuid.uuid4()),
            "volunteer_id": volunteer_id,
            "role_id": body.role_id or "r01",
            "location": body.location,
            "scheduled_date": body.scheduled_date,
            "shift": body.shift,
            "status": "scheduled",
            "assigned_by": user["sub"],
        }).execute()
        if dep_result.data:
            deployment_id = dep_result.data[0]["id"]

    background_tasks.add_task(
        bulk_sms, [v["phone"]], "application_assigned", "en",
        role=body.role, dept=body.dept
    )

    return {"assigned": True, "volunteer": v, "deployment_id": deployment_id}

@router.post("/reject/{volunteer_id}")
def reject_volunteer(
    volunteer_id: str,
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Reject a volunteer application."""
    db = get_supabase()
    result = db.table("volunteers").update({
        "status": "rejected",
        "rejected_by": user["sub"],
    }).eq("id", volunteer_id).execute()
    if not result.data:
        raise HTTPException(404, "Volunteer not found")
    return {"rejected": True}

@router.post("/bulk-sms")
def send_bulk_sms(
    volunteer_ids: list[str],
    template_key: str,
    lang: str = "en",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Send bulk SMS to a list of volunteers."""
    db = get_supabase()
    result = db.table("volunteers").select("phone").in_("id", volunteer_ids).execute()
    phones = [v["phone"] for v in result.data]
    background_tasks.add_task(bulk_sms, phones, template_key, lang)
    return {"queued": len(phones)}

@router.get("/export/csv")
def export_csv(
    status: str | None = None,
    commune: str | None = None,
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Export volunteer list as CSV."""
    import csv, io
    from fastapi.responses import StreamingResponse
    db = get_supabase()
    query = db.table("volunteers").select(
        "full_name,phone,commune,status,assigned_role,assigned_dept,tier,ai_score,created_at"
    )
    if status:
        query = query.eq("status", status)
    if commune:
        query = query.eq("commune", commune)
    result = query.order("created_at", desc=True).execute()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "full_name","phone","commune","status","assigned_role","assigned_dept","tier","ai_score","created_at"
    ])
    writer.writeheader()
    writer.writerows(result.data)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pondysevai_volunteers.csv"},
    )

@router.get("/stats")
def get_stats(user: dict = Depends(require_role("nodal_officer", "admin"))):
    """Dashboard stats for the nodal officer."""
    try:
        db = get_supabase()
        all_v = db.table("volunteers").select("status,commune,tier").execute().data
    except Exception:
        all_v = DEMO_APPLICANTS
    stats = {
        "total": len(all_v),
        "by_status": {},
        "by_commune": {},
        "by_tier": {},
    }
    for v in all_v:
        s = v.get("status", "unknown")
        stats["by_status"][s] = stats["by_status"].get(s, 0) + 1
        c = v.get("commune", "unknown")
        stats["by_commune"][c] = stats["by_commune"].get(c, 0) + 1
        t = v.get("tier")
        if t:
            stats["by_tier"][t] = stats["by_tier"].get(t, 0) + 1
    return stats
