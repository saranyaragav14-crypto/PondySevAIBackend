"""
Notification service — SMS via Twilio, WhatsApp via Twilio WhatsApp API.
Falls back to console log in dev mode.
"""
from app.config import get_settings

settings = get_settings()

TEMPLATES = {
    "registration_success": {
        "en": "Welcome to PondySevAi! Your reference number is {ref}. Your application will be reviewed within 3-5 days.",
        "ta": "PondySevAi க்கு வரவேற்கிறோம்! உங்கள் குறிப்பு எண்: {ref}. 3-5 நாட்களுக்குள் மதிப்பாய்வு செய்யப்படும்.",
        "fr": "Bienvenue sur PondySevAi ! Votre numéro de référence est {ref}. Votre candidature sera examinée sous 3 à 5 jours.",
    },
    "application_assigned": {
        "en": "Congratulations! You have been assigned the role of {role} in {dept}. Log in to your dashboard for details.",
        "ta": "வாழ்த்துக்கள்! {dept} இல் {role} பங்கு உங்களுக்கு நியமிக்கப்பட்டது. விவரங்களுக்கு உங்கள் டாஷ்போர்டில் உள்நுழையவும்.",
        "fr": "Félicitations ! Vous avez été assigné(e) au rôle de {role} dans {dept}. Connectez-vous à votre tableau de bord pour les détails.",
    },
    "deployment_reminder": {
        "en": "Reminder: Your deployment is tomorrow at {time}, {location}. Don't forget your ID card!",
        "ta": "நினைவூட்டல்: உங்கள் பணி நாளை {time} மணிக்கு {location} இல் உள்ளது. உங்கள் அடையாள அட்டையை மறக்காதீர்கள்!",
        "fr": "Rappel : Votre déploiement est demain à {time}, {location}. N'oubliez pas votre carte d'identité !",
    },
    "certificate_ready": {
        "en": "Your {tier} certificate is ready! Download it from your dashboard: {url}",
        "ta": "உங்கள் {tier} சான்றிதழ் தயாராக உள்ளது! உங்கள் டாஷ்போர்டில் இருந்து பதிவிறக்கவும்: {url}",
        "fr": "Votre certificat {tier} est prêt ! Téléchargez-le depuis votre tableau de bord : {url}",
    },
    "otp": {
        "en": "Your PondySevAi OTP is: {otp}. Valid for 10 minutes. Do not share this with anyone.",
        "ta": "உங்கள் PondySevAi OTP: {otp}. 10 நிமிடங்களுக்கு செல்லுபடியாகும். யாரிடமும் பகிர வேண்டாம்.",
        "fr": "Votre OTP PondySevAi est : {otp}. Valable 10 minutes. Ne le partagez avec personne.",
    },
}

def _get_template(template_key: str, lang: str, **kwargs) -> str:
    tmpl = TEMPLATES.get(template_key, {})
    text = tmpl.get(lang, tmpl.get("en", ""))
    return text.format(**kwargs)

def send_sms(phone: str, template_key: str, lang: str = "en", **kwargs) -> bool:
    message = _get_template(template_key, lang, **kwargs)
    if settings.app_env != "production" or not settings.twilio_account_sid:
        print(f"[SMS dev] +91{phone}: {message}")
        return True
    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(body=message, from_=settings.twilio_from_number, to=f"+91{phone}")
        return True
    except Exception as e:
        print(f"[SMS error] {e}")
        return False

def send_whatsapp(phone: str, template_key: str, lang: str = "en", **kwargs) -> bool:
    message = _get_template(template_key, lang, **kwargs)
    if settings.app_env != "production" or not settings.twilio_account_sid:
        print(f"[WhatsApp dev] +91{phone}: {message}")
        return True
    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            body=message,
            from_=f"whatsapp:{settings.twilio_from_number}",
            to=f"whatsapp:+91{phone}",
        )
        return True
    except Exception as e:
        print(f"[WhatsApp error] {e}")
        return False

def bulk_sms(phones: list[str], template_key: str, lang: str = "en", **kwargs) -> dict:
    results = {"sent": 0, "failed": 0}
    for phone in phones:
        if send_sms(phone, template_key, lang, **kwargs):
            results["sent"] += 1
        else:
            results["failed"] += 1
    return results
