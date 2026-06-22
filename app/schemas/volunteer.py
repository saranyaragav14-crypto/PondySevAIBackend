from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date
import re

class VolunteerCreate(BaseModel):
    full_name: str
    dob: date
    phone: str
    email: Optional[str] = None
    commune: str
    address: Optional[str] = None
    gender: Optional[str] = None
    languages: list[str] = []
    qualifications: list[str] = []
    availability: list[str] = []
    mobility_impairment: bool = False
    experience: Optional[str] = None
    departments: list[str] = []
    motivation: Optional[str] = None
    role_type: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_10_digits(cls, v):
        digits = re.sub(r'\D', '', v)
        if len(digits) != 10:
            raise ValueError("Phone must be exactly 10 digits")
        return digits

    @field_validator("commune")
    @classmethod
    def valid_commune(cls, v):
        valid = ["Puducherry", "Villianur", "Bahour", "Ariyankuppam"]
        if v not in valid:
            raise ValueError(f"Commune must be one of {valid}")
        return v

class VolunteerOut(BaseModel):
    id: str
    full_name: str
    phone: str
    commune: str
    status: str
    reference_number: str
    tier: Optional[str] = None
    ai_assessment: Optional[str] = None
    ai_score: Optional[float] = None
    ai_top_matches: Optional[str] = None
    assigned_role: Optional[str] = None
    assigned_dept: Optional[str] = None
    availability: list[str] = []
    departments: list[str] = []

class VolunteerUpdate(BaseModel):
    status: Optional[str] = None
    assigned_role: Optional[str] = None
    assigned_dept: Optional[str] = None
    tier: Optional[str] = None
    nodal_officer_notes: Optional[str] = None
