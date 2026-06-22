"""
AI matching service — two layers:
Layer 1: MiniLM sentence-transformers (cosine similarity, CPU-only)
Layer 2: Claude API (natural language profile assessment)
"""
import json
import traceback
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
        print("[AI matching] Loading SentenceTransformer model...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        print("[AI matching] Model loaded successfully.")
    return _model

def _fallback_role_matches(volunteer: dict, roles: list[dict]) -> list[dict]:
    preferred = set(volunteer.get("departments") or [])
    scored = []
    for role in roles:
      if volunteer.get("mobility_impairment") and role.get("demand") == "high":
          continue
      score = 0.72 if role.get("dept_name") in preferred or role.get("dept_id") in preferred else 0.52
      scored.append({
          "role_id": role["id"],
          "role_name": role["name"],
          "dept": role.get("dept_name", ""),
          "demand": role.get("demand", ""),
          "score": score,
      })
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:5]

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

def compute_role_matches(volunteer: dict) -> list[dict]:
    """
    Layer 1: MiniLM matching.
    Returns list of {role_id, role_name, dept, score} sorted by score desc.
    Only includes scores >= 0.45. High-demand roles filtered if mobility_impairment.
    """
    try:
        db = get_supabase()
        roles_result = db.table("roles").select("*").execute()
        roles = roles_result.data

        print(f"[AI matching] Found {len(roles)} roles in database.")

        if not roles:
            print("[AI matching] No roles found — skipping matching.")
            return []

        try:
            model = _get_model()
            import numpy as np
        except Exception as e:
            print(f"[AI matching] SentenceTransformer unavailable, using fallback matcher: {e}")
            return _fallback_role_matches(volunteer, roles)

        profile_text = _build_profile_text(volunteer)
        print(f"[AI matching] Profile text: {profile_text}")
        profile_vec = model.encode(profile_text, normalize_embeddings=True)

        scored = []
        for role in roles:
            # Hard filter: skip high-demand roles for mobility-impaired volunteers
            if volunteer.get("mobility_impairment") and role.get("demand") == "high":
                continue

            role_text = f"{role['name']}. Required qualifications: {role.get('qualifications', '')}. Department: {role.get('dept_name', '')}"
            role_vec = model.encode(role_text, normalize_embeddings=True)
            score = float(np.dot(profile_vec, role_vec) / (np.linalg.norm(profile_vec) * np.linalg.norm(role_vec) + 1e-9))

            if score >= 0.45:
                scored.append({
                    "role_id": role["id"],
                    "role_name": role["name"],
                    "dept": role.get("dept_name", ""),
                    "demand": role.get("demand", ""),
                    "score": round(score, 4),
                })

        print(f"[AI matching] {len(scored)} roles matched above threshold 0.45.")
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:5]

    except Exception as e:
        print(f"[AI matching] Error in compute_role_matches: {e}")
        traceback.print_exc()
        return []

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

    try:
        response = _anthropic.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[AI matching] Claude API error: {e}")
        traceback.print_exc()
        return f"AI narrative unavailable. Top match: {top_matches[0]['role_name']} ({top_matches[0]['dept']})."

def run_full_assessment(volunteer_id: str) -> dict:
    """
    Full pipeline: fetch volunteer → MiniLM matching → Claude assessment → save to DB.
    Called as a background job after registration.
    """
    try:
        print(f"[AI matching] Starting assessment for volunteer {volunteer_id}")
        db = get_supabase()
        vol_result = db.table("volunteers").select("*").eq("id", volunteer_id).execute()
        if not vol_result.data:
            print(f"[AI matching] Volunteer {volunteer_id} not found.")
            return {"error": "Volunteer not found"}

        volunteer = vol_result.data[0]
        top_matches = compute_role_matches(volunteer)
        ai_score = top_matches[0]["score"] if top_matches else 0.0
        assessment = generate_claude_assessment(volunteer, top_matches)

        print(f"[AI matching] Score: {ai_score}, Matches: {len(top_matches)}, Assessment: {assessment[:80]}")

        # Save assessment back to volunteer record
        db.table("volunteers").update({
            "ai_assessment": assessment,
            "ai_score": ai_score,
            "ai_top_matches": json.dumps(top_matches),
            "status": "pending_review",
        }).eq("id", volunteer_id).execute()

        print(f"[AI matching] Assessment saved for volunteer {volunteer_id}")
        return {
            "volunteer_id": volunteer_id,
            "top_matches": top_matches,
            "ai_score": ai_score,
            "assessment": assessment,
        }
    except Exception as e:
        print(f"[AI matching] Fatal error in run_full_assessment: {e}")
        traceback.print_exc()
        return {"error": str(e)}
