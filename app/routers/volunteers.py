import uuid
import random
import string
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.schemas.volunteer import VolunteerCreate, VolunteerOut, VolunteerUpdate
from app.database import get_supabase
from app.services.notifications import send_sms
from app.services import fallback_data
from app.services import auth as auth_service
from app.routers.auth import get_current_user, require_role

router = APIRouter(prefix="/volunteers", tags=["volunteers"])

def _gen_ref() -> str:
    return "PSA-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@router.post("/register", response_model=VolunteerOut, status_code=201)
def register_volunteer(body: VolunteerCreate, background_tasks: BackgroundTasks):
    """Register a new volunteer. Triggers AI assessment in the background."""
    volunteer_id = str(uuid.uuid4())
    ref = _gen_ref()

    record = {
        "id": volunteer_id,
        "reference_number": ref,
        "full_name": body.full_name,
        "dob": str(body.dob),
        "phone": body.phone,
        "email": body.email,
        "commune": body.commune,
        "address": body.address,
        "gender": body.gender,
        "languages": body.languages,
        "qualifications": body.qualifications,
        "availability": body.availability,
        "mobility_impairment": body.mobility_impairment,
        "experience": body.experience,
        "departments": body.departments,
        "motivation": body.motivation,
        "role_type": body.role_type,
        "status": "registered",
        "tier": None,
        "ai_assessment": None,
        "ai_score": None,
    }

    try:
        db = get_supabase()
        existing = db.table("volunteers").select("id").eq("phone", body.phone).execute()
        if existing.data:
            raise HTTPException(409, "A volunteer with this phone number already exists")

        result = db.table("volunteers").insert(record).execute()
        if not result.data:
            raise HTTPException(500, "Failed to save volunteer record")

        background_tasks.add_task(send_sms, body.phone, "registration_success", "en", ref=ref)
        background_tasks.add_task(_run_ai_assessment, volunteer_id)
    except HTTPException:
        raise
    except Exception as exc:
        fallback_data.add_volunteer(record)
        print(f"[registration fallback] Supabase unavailable; saved fallback reference {ref}: {exc}")

    return VolunteerOut(
        id=volunteer_id,
        full_name=body.full_name,
        phone=body.phone,
        commune=body.commune,
        status="registered",
        reference_number=ref,
    )


def _run_ai_assessment(volunteer_id: str):
    """Background task — run MiniLM + Claude assessment."""
    try:
        from app.services.ai_matching import run_full_assessment
        run_full_assessment(volunteer_id)
    except Exception as e:
        import traceback
        print(f"[AI assessment error] volunteer {volunteer_id}: {e}")
        traceback.print_exc()


@router.get("/me", response_model=VolunteerOut)
def get_my_profile(user: dict = Depends(get_current_user)):
    """Get logged-in volunteer's profile."""
    try:
        db = get_supabase()
        result = db.table("volunteers").select("*").eq("id", user["sub"]).execute()
        v = result.data[0] if result.data else fallback_data.get_by_id(user["sub"])
        if not v and user.get("phone"):
            result = db.table("volunteers").select("*").eq("phone", user["phone"]).execute()
            v = result.data[0] if result.data else fallback_data.get_by_phone(user["phone"])
    except Exception:
        v = fallback_data.get_by_id(user["sub"])
    if not v and user.get("phone"):
        v = fallback_data.get_by_phone(user["phone"])
    if not v and user.get("phone"):
        v = auth_service.get_fallback_volunteer(user["phone"])
    if not v:
        raise HTTPException(404, "Volunteer not found")
    return VolunteerOut(**v)


@router.get("/{volunteer_id}", response_model=VolunteerOut)
def get_volunteer(volunteer_id: str, user: dict = Depends(require_role("nodal_officer", "admin"))):
    """Get volunteer by ID (nodal officer / admin only)."""
    try:
        db = get_supabase()
        result = db.table("volunteers").select("*").eq("id", volunteer_id).execute()
        volunteer = result.data[0] if result.data else fallback_data.get_by_id(volunteer_id)
    except Exception:
        volunteer = fallback_data.get_by_id(volunteer_id)
    if not volunteer:
        raise HTTPException(404, "Volunteer not found")
    return VolunteerOut(**volunteer)


@router.get("/")
def list_volunteers(
    status: str | None = None,
    commune: str | None = None,
    dept: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """List all volunteers with optional filters (nodal officer / admin only)."""
    try:
        db = get_supabase()
        query = db.table("volunteers").select("*")
        if status:
            query = query.eq("status", status)
        if commune:
            query = query.eq("commune", commune)
        result = query.range(offset, offset + limit - 1).order("created_at", desc=True).execute()
        volunteers = result.data or []
    except Exception:
        volunteers = []
    fallback_volunteers = fallback_data.list_volunteers(status=status, commune=commune)
    volunteers_by_key = {
        volunteer.get("phone") or volunteer.get("id"): volunteer
        for volunteer in volunteers
    }
    for volunteer in fallback_volunteers:
        volunteers_by_key[volunteer.get("phone") or volunteer.get("id")] = volunteer
    volunteers = list(volunteers_by_key.values())
    return {"volunteers": volunteers, "total": len(volunteers)}


@router.patch("/{volunteer_id}")
def update_volunteer(
    volunteer_id: str,
    body: VolunteerUpdate,
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Update volunteer status / assignment (nodal officer / admin only)."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")

    try:
        db = get_supabase()
        result = db.table("volunteers").update(updates).eq("id", volunteer_id).execute()
        volunteer = result.data[0] if result.data else fallback_data.update_volunteer(volunteer_id, updates)
    except Exception:
        volunteer = fallback_data.update_volunteer(volunteer_id, updates)
    if not volunteer:
        raise HTTPException(404, "Volunteer not found")

    if body.status == "assigned" and body.assigned_role:
        send_sms(volunteer["phone"], "application_assigned", "en",
                 role=body.assigned_role, dept=body.assigned_dept or "Government of Puducherry")

    return {"updated": True, "volunteer": volunteer}


@router.post("/{volunteer_id}/reassess")
def trigger_reassessment(
    volunteer_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("nodal_officer", "admin")),
):
    """Manually trigger AI reassessment for a volunteer."""
    background_tasks.add_task(_run_ai_assessment, volunteer_id)
    return {"message": "AI reassessment queued"}
