from fastapi import APIRouter, HTTPException, Depends, Response
from app.database import get_supabase
from app.routers.auth import get_current_user

router = APIRouter(prefix="/certificates", tags=["certificates"])

@router.get("/download/{volunteer_id}")
def download_certificate(volunteer_id: str, user: dict = Depends(get_current_user)):
    """Generate and download QR-verifiable PDF certificate."""
    if user["sub"] != volunteer_id and user.get("role") not in ("nodal_officer", "admin"):
        raise HTTPException(403, "Not authorised")

    db = get_supabase()
    vol = db.table("volunteers").select("full_name,commune,tier").eq("id", volunteer_id).execute()
    if not vol.data:
        raise HTTPException(404, "Volunteer not found")

    volunteer = vol.data[0]
    tier = volunteer.get("tier")
    if not tier:
        raise HTTPException(400, "Volunteer has not yet earned a tier")

    from app.services.certificate import generate_certificate
    pdf_bytes = generate_certificate(volunteer_id, tier)

    name_slug = volunteer["full_name"].replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=PondySevAi_{name_slug}_{tier}.pdf"},
    )

@router.get("/verify/{cert_id}")
def verify_certificate(cert_id: str):
    """Public QR code verification endpoint."""
    db = get_supabase()
    result = db.table("certificates").select(
        "*, volunteers(full_name, commune, tier)"
    ).eq("id", cert_id).execute()
    if not result.data:
        raise HTTPException(404, "Certificate not found or invalid")
    cert = result.data[0]
    return {
        "valid": True,
        "cert_id": cert_id,
        "volunteer_name": cert["volunteers"]["full_name"],
        "commune": cert["volunteers"]["commune"],
        "tier": cert["volunteers"]["tier"],
        "issued_date": cert["issued_date"],
    }

@router.get("/my")
def my_certificates(user: dict = Depends(get_current_user)):
    """List all certificates for the logged-in volunteer."""
    db = get_supabase()
    result = db.table("certificates").select("*").eq("volunteer_id", user["sub"]).execute()
    return {"certificates": result.data}
