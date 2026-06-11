from fastapi import APIRouter, Depends
from app.database import get_supabase

router = APIRouter(prefix="/rewards", tags=["rewards"])

@router.get("/leaderboard")
def get_leaderboard(commune: str | None = None):
    """Public leaderboard — top volunteers by completed deployment months."""
    db = get_supabase()

    query = db.table("volunteers").select(
        "id,full_name,commune,assigned_dept,tier,latest_feedback"
    ).eq("status", "assigned").order("tier", desc=True)

    if commune:
        query = query.eq("commune", commune)

    volunteers = query.execute().data

    # Get completed deployment counts for each volunteer
    leaderboard = []
    for v in volunteers:
        completed = db.table("deployments").select("scheduled_date").eq(
            "volunteer_id", v["id"]
        ).eq("status", "completed").execute()
        months = len(set(d["scheduled_date"][:7] for d in completed.data)) if completed.data else 0
        leaderboard.append({
            **v,
            "completed_months": months,
        })

    # Sort by tier then months
    tier_order = {"platinum": 4, "gold": 3, "silver": 2, "bronze": 1, None: 0}
    leaderboard.sort(key=lambda x: (tier_order.get(x.get("tier"), 0), x["completed_months"]), reverse=True)

    return {"leaderboard": leaderboard[:50]}