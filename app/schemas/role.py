from pydantic import BaseModel
from typing import Optional

class RoleOut(BaseModel):
    id: str
    name: str
    dept_id: str
    dept_name: str
    qualifications: str
    demand: str
    description: Optional[str] = None

class DeploymentCreate(BaseModel):
    volunteer_id: str
    role_id: str
    location: str
    scheduled_date: str
    shift: str

class CheckInOut(BaseModel):
    volunteer_id: str
    deployment_id: str
    action: str  # "checkin" | "checkout"

class FeedbackCreate(BaseModel):
    volunteer_id: str
    deployment_id: str
    category: str  # "top_performer" | "performer" | "regular"
    notes: Optional[str] = None
