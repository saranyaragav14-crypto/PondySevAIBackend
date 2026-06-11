"""
Certificate generation service.
Produces QR-verifiable PDF certificates using reportlab canvas for precise layout.
"""
import io
import uuid
import qrcode
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from app.config import get_settings
from app.database import get_supabase

settings = get_settings()

W, H = A4  # 210 x 297 mm

TIER_CONFIG = {
    "bronze":   {"color": colors.HexColor("#B45309"), "light": colors.HexColor("#FEF3C7"), "border": colors.HexColor("#D97706"), "label": "Bronze"},
    "silver":   {"color": colors.HexColor("#475569"), "light": colors.HexColor("#F1F5F9"), "border": colors.HexColor("#94A3B8"), "label": "Silver"},
    "gold":     {"color": colors.HexColor("#B45309"), "light": colors.HexColor("#FEFCE8"), "border": colors.HexColor("#EAB308"), "label": "Gold"},
    "platinum": {"color": colors.HexColor("#334155"), "light": colors.HexColor("#F8FAFC"), "border": colors.HexColor("#7C3AED"), "label": "Platinum"},
}

def _make_qr_bytes(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(box_size=6, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1A2B4A", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def generate_certificate(volunteer_id: str, tier: str) -> bytes:
    db = get_supabase()
    vol = db.table("volunteers").select("*").eq("id", volunteer_id).execute().data
    if not vol:
        raise ValueError("Volunteer not found")

    volunteer = vol[0]
    cert_id = str(uuid.uuid4())[:8].upper()
    verify_url = f"{settings.frontend_url}/verify/{cert_id}"
    issued_date = datetime.now().strftime("%d %B %Y")
    tc = TIER_CONFIG.get(tier.lower(), TIER_CONFIG["bronze"])

    # Save cert record
    db.table("certificates").upsert({
        "id": cert_id,
        "volunteer_id": volunteer_id,
        "tier": tier,
        "issued_date": datetime.now().isoformat(),
        "verify_url": verify_url,
    }).execute()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # ── Background ──────────────────────────────────────
    c.setFillColor(colors.HexColor("#FAFAF9"))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # ── Outer decorative border ──────────────────────────
    c.setStrokeColor(tc["border"])
    c.setLineWidth(3)
    c.rect(12*mm, 12*mm, W - 24*mm, H - 24*mm, fill=0, stroke=1)

    c.setStrokeColor(tc["color"])
    c.setLineWidth(1)
    c.rect(15*mm, 15*mm, W - 30*mm, H - 30*mm, fill=0, stroke=1)

    # ── Top header band ──────────────────────────────────
    c.setFillColor(colors.HexColor("#1A2B4A"))
    c.rect(12*mm, H - 52*mm, W - 24*mm, 40*mm, fill=1, stroke=0)

    # Government of Puducherry
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(W/2, H - 27*mm, "GOVERNMENT OF PUDUCHERRY")

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.drawCentredString(W/2, H - 33*mm, "Union Territory of Puducherry")

    c.setFont("Helvetica", 9)
    c.setFillColor(tc["border"])
    c.drawCentredString(W/2, H - 40*mm, "PondySevAi — AI-Powered Civic Volunteer Programme")

    # ── Tier badge ───────────────────────────────────────
    badge_y = H - 72*mm
    c.setFillColor(tc["light"])
    c.setStrokeColor(tc["border"])
    c.setLineWidth(1.5)
    c.roundRect(W/2 - 45*mm, badge_y - 8*mm, 90*mm, 16*mm, 8*mm, fill=1, stroke=1)
    c.setFillColor(tc["color"])
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W/2, badge_y - 1*mm, f"🏅  {tc['label'].upper()} VOLUNTEER CERTIFICATE")

    # ── Divider ──────────────────────────────────────────
    c.setStrokeColor(tc["border"])
    c.setLineWidth(0.5)
    c.line(25*mm, H - 82*mm, W - 25*mm, H - 82*mm)

    # ── Certificate body ─────────────────────────────────
    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(W/2, H - 95*mm, "This is to certify that")

    # Volunteer name
    name = volunteer["full_name"]
    c.setFillColor(colors.HexColor("#1A2B4A"))
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(W/2, H - 110*mm, name)

    # Name underline
    name_w = c.stringWidth(name, "Helvetica-Bold", 26)
    c.setStrokeColor(tc["border"])
    c.setLineWidth(1.5)
    c.line(W/2 - name_w/2, H - 113*mm, W/2 + name_w/2, H - 113*mm)

    # Body text
    c.setFillColor(colors.HexColor("#444444"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(W/2, H - 122*mm, f"has successfully completed {tc['label']} Tier volunteer service")
    c.drawCentredString(W/2, H - 129*mm, "with the Government of Puducherry through the PondySevAi platform.")

    # ── Details box ──────────────────────────────────────
    box_y = H - 160*mm
    c.setFillColor(tc["light"])
    c.setStrokeColor(tc["border"])
    c.setLineWidth(0.5)
    c.roundRect(35*mm, box_y - 6*mm, W - 70*mm, 28*mm, 4*mm, fill=1, stroke=1)

    details = [
        ("Commune", volunteer.get("commune", "Puducherry")),
        ("Department", volunteer.get("assigned_dept") or "Civic Volunteer"),
        ("Date of Issue", issued_date),
        ("Tier", tc["label"]),
    ]
    col_w = (W - 70*mm) / 2
    for i, (label, value) in enumerate(details):
        col = i % 2
        row = i // 2
        x = 40*mm + col * col_w
        y = box_y + 14*mm - row * 11*mm
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont("Helvetica", 8)
        c.drawString(x, y, label.upper())
        c.setFillColor(colors.HexColor("#1A2B4A"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, y - 5*mm, value)

    # ── QR code ──────────────────────────────────────────
    qr_buf = _make_qr_bytes(verify_url)
    qr_img = ImageReader(qr_buf)
    qr_size = 28*mm
    qr_x = W/2 - qr_size/2
    qr_y = H - 210*mm

    # QR white background
    c.setFillColor(colors.white)
    c.setStrokeColor(tc["border"])
    c.setLineWidth(0.5)
    c.roundRect(qr_x - 3*mm, qr_y - 3*mm, qr_size + 6*mm, qr_size + 6*mm, 3*mm, fill=1, stroke=1)
    c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size, preserveAspectRatio=True)

    # QR labels
    c.setFillColor(colors.HexColor("#888888"))
    c.setFont("Helvetica", 7)
    c.drawCentredString(W/2, qr_y - 7*mm, "Scan to verify certificate")

    c.setFillColor(colors.HexColor("#1A2B4A"))
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W/2, H - 218*mm, f"Certificate ID: {cert_id}")

    c.setFillColor(colors.HexColor("#AAAAAA"))
    c.setFont("Helvetica", 7)
    c.drawCentredString(W/2, H - 223*mm, verify_url)

    # ── Signature line ───────────────────────────────────
    sig_y = H - 245*mm
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.setLineWidth(0.5)
    c.line(30*mm, sig_y, 90*mm, sig_y)
    c.line(W - 90*mm, sig_y, W - 30*mm, sig_y)

    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(60*mm, sig_y - 5*mm, "Nodal Officer")
    c.drawCentredString(W - 60*mm, sig_y - 5*mm, "Programme Director")
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#AAAAAA"))
    c.drawCentredString(60*mm, sig_y - 9*mm, "PondySevAi")
    c.drawCentredString(W - 60*mm, sig_y - 9*mm, "Decision Minds")

    # ── Footer ───────────────────────────────────────────
    c.setFillColor(colors.HexColor("#1A2B4A"))
    c.rect(12*mm, 12*mm, W - 24*mm, 18*mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(W/2, 23*mm, "An Initiative by Decision Minds  ·  Powered by Anthropic Claude AI")
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.drawCentredString(W/2, 18*mm, "pondysevai.vercel.app  ·  Government of Puducherry, India")

    c.save()
    return buf.getvalue()