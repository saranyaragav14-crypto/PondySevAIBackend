"""
AI matching service — two layers:
Layer 1: MiniLM sentence-transformers (cosine similarity, CPU-only)
Layer 2: Claude API (natural language profile assessment)
"""
import json
import numpy as np
from typing import Optional
from anthropic import Anthropic
from app.config import get_settings
from app.database import get_supabase

settings = get_settings()
_anthropic = Anthropic(api_key=settings.anthropic_api_key)

# Lazy-load the model so startup is fast
_model = None

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model

def _build_profile_text(volunteer: dict) -> str:
    """Flatten volunteer profile into a single text for embedding."""
    parts = [
        f"Name: {volunteer.get('full_name', '')}",
        f"Languages: {', '.join(volunteer.get('languages', []))}",
        f"Qualifications: {', '.join(volunteer.get('qualifications', []))}",
        f"Availability: {', '.join(volunteer.get('availability', []))}",
        f"Experience: {volunteer.get('experience', '')}",
        f"Preferred departments: {', '.join(volunteer.get('departments', []))}",
        f"Motivation: {volunteer.get('motivation', '')}",
        f"Mobility impairment: {'yes' if volunteer.get('mobility_impairment') else 'no'}",
    ]
    return ". ".join(p for p in parts if p.split(": ", 1)[1])

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

def compute_role_matches(volunteer: dict) -> list[dict]:
    """
    Layer 1: MiniLM matching.
    Returns list of {role_id, role_name, dept, score} sorted by score desc.
    Only includes scores >= 0.65. High-demand roles filtered if mobility_impairment.
    """
    db = get_supabase()
    roles_result = db.table("roles").select("*").execute()
    roles = roles_result.data

    if not roles:
        return []

    model = _get_model()
    profile_text = _build_profile_text(volunteer)
    profile_vec = model.encode(profile_text, normalize_embeddings=True)

    scored = []
    for role in roles:
        # Hard filter: skip high-demand roles for mobility-impaired volunteers
        if volunteer.get("mobility_impairment") and role.get("demand") == "high":
            continue

        role_text = f"{role['name']}. {role.get('description', '')}. Required: {role.get('qualifications', '')}"
        role_vec = model.encode(role_text, normalize_embeddings=True)
        score = _cosine_similarity(profile_vec, role_vec)

        if score >= 0.65:
            scored.append({
                "role_id": role["id"],
                "role_name": role["name"],
                "dept": role.get("dept_name", ""),
                "demand": role.get("demand", ""),
                "score": round(score, 4),
            })

    return sorted(scored, key=lambda x: x["score"], reverse=True)[:5]

def generate_claude_assessment(volunteer: dict, top_matches: list[dict]) -> str:
    """
    Layer 2: Claude API assessment.
    Generates a 2-3 sentence human-readable summary for the nodal officer.
    """
    if not settings.anthropic_api_key:
        return "AI assessment unavailable — ANTHROPIC_API_KEY not configured."

    if not top_matches:
        return "No strong role matches found for this volunteer profile."

    roles_text = "\n".join(
        f"- {m['role_name']} ({m['dept']}) — score {m['score']:.2f}"
        for m in top_matches[:3]
    )

    prompt = f"""You are an assistant helping a nodal officer in Puducherry's government volunteer platform.
Review this volunteer's profile and write a 2-3 sentence assessment for the officer.
Be specific, factual, and helpful. Focus on what makes this person suitable (or not) for civic volunteer work.
End with your top role recommendation.

Volunteer profile:
- Name: {volunteer.get('full_name')}
- Languages: {', '.join(volunteer.get('languages', []))}
- Qualifications: {', '.join(volunteer.get('qualifications', []))}
- Availability: {', '.join(volunteer.get('availability', []))}
- Experience: {volunteer.get('experience', 'None provided')}
- Preferred departments: {', '.join(volunteer.get('departments', []))}
- Motivation: {volunteer.get('motivation', 'None provided')}
- Mobility impairment: {'Yes' if volunteer.get('mobility_impairment') else 'No'}

Top matched roles:
{roles_text}

Write the assessment in English, 2-3 sentences only."""

    response = _anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()

def run_full_assessment(volunteer_id: str) -> dict:
    """
    Full pipeline: fetch volunteer → MiniLM matching → Claude assessment → save to DB.
    Called as a background job after registration.
    """
    db = get_supabase()
    vol_result = db.table("volunteers").select("*").eq("id", volunteer_id).execute()
    if not vol_result.data:
        return {"error": "Volunteer not found"}

    volunteer = vol_result.data[0]
    top_matches = compute_role_matches(volunteer)
    ai_score = top_matches[0]["score"] if top_matches else 0.0
    assessment = generate_claude_assessment(volunteer, top_matches)

    # Save assessment back to volunteer record
    db.table("volunteers").update({
        "ai_assessment": assessment,
        "ai_score": ai_score,
        "ai_top_matches": json.dumps(top_matches),
        "status": "pending_review",
    }).eq("id", volunteer_id).execute()

    return {
        "volunteer_id": volunteer_id,
        "top_matches": top_matches,
        "ai_score": ai_score,
        "assessment": assessment,
    }
