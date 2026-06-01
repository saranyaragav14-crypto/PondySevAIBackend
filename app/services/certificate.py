"""
Certificate generation service.
Produces QR-verifiable PDF certificates using reportlab + qrcode.
"""
import io
import uuid
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from app.config import get_settings
from app.database import get_supabase

settings = get_settings()

TIER_COLORS = {
    "bronze":   colors.HexColor("#B45309"),
    "silver":   colors.HexColor("#64748B"),
    "gold":     colors.HexColor("#D97706"),
    "platinum": colors.HexColor("#334155"),
}

def _make_qr_image(data: str, size: int = 100) -> Image:
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=size, height=size)

def generate_certificate(volunteer_id: str, tier: str) -> bytes:
    """
    Generate a QR-verifiable PDF certificate for a volunteer.
    Returns raw PDF bytes.
    """
    db = get_supabase()
    vol = db.table("volunteers").select("*").eq("id", volunteer_id).execute().data
    if not vol:
        raise ValueError("Volunteer not found")

    volunteer = vol[0]
    cert_id = str(uuid.uuid4())[:8].upper()
    verify_url = f"{settings.frontend_url}/verify/{cert_id}"
    issued_date = datetime.now().strftime("%d %B %Y")
    tier_label = tier.capitalize()
    tier_color = TIER_COLORS.get(tier.lower(), colors.grey)

    # Save cert record to DB
    db.table("certificates").insert({
        "id": cert_id,
        "volunteer_id": volunteer_id,
        "tier": tier,
        "issued_date": datetime.now().isoformat(),
        "verify_url": verify_url,
    }).execute()

    # Build PDF
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("title", parent=styles["Normal"],
                                  fontSize=28, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER, textColor=colors.HexColor("#1A2B4A"),
                                  spaceAfter=6)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"],
                                fontSize=13, fontName="Helvetica",
                                alignment=TA_CENTER, textColor=colors.grey,
                                spaceAfter=4)
    name_style = ParagraphStyle("name", parent=styles["Normal"],
                                 fontSize=22, fontName="Helvetica-Bold",
                                 alignment=TA_CENTER, textColor=tier_color,
                                 spaceAfter=4)
    body_style = ParagraphStyle("body", parent=styles["Normal"],
                                 fontSize=11, fontName="Helvetica",
                                 alignment=TA_CENTER, textColor=colors.HexColor("#444"),
                                 spaceAfter=4)

    story = [
        Spacer(1, 10*mm),
        Paragraph("🏛️ GOVERNMENT OF PUDUCHERRY", sub_style),
        Paragraph("PondySevAi Civic Volunteer Programme", sub_style),
        Spacer(1, 8*mm),
        Paragraph(f"<font color='#{tier_color.hexval()[2:]}'>— {tier_label} Volunteer Certificate —</font>", title_style),
        Spacer(1, 8*mm),
        Paragraph("This is to certify that", body_style),
        Paragraph(volunteer["full_name"], name_style),
        Paragraph(f"has successfully completed <b>{tier_label} tier</b> volunteer service", body_style),
        Paragraph("with the Government of Puducherry through the PondySevAi platform.", body_style),
        Spacer(1, 6*mm),
        Paragraph(f"Commune: <b>{volunteer['commune']}</b>", body_style),
        Paragraph(f"Date of Issue: <b>{issued_date}</b>", body_style),
        Spacer(1, 10*mm),
        _make_qr_image(verify_url, size=90),
        Spacer(1, 4*mm),
        Paragraph(f"Certificate ID: <b>{cert_id}</b>", body_style),
        Paragraph(f"Verify at: {verify_url}", ParagraphStyle("small", parent=styles["Normal"],
                  fontSize=8, alignment=TA_CENTER, textColor=colors.grey)),
        Spacer(1, 10*mm),
        Paragraph("An Initiative by <b>Decision Minds</b>", body_style),
        Paragraph("Powered by Anthropic Claude API", ParagraphStyle("tiny", parent=styles["Normal"],
                  fontSize=8, alignment=TA_CENTER, textColor=colors.lightgrey)),
    ]

    doc.build(story)
    return buf.getvalue()
