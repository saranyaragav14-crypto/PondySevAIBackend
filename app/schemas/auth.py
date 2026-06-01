from pydantic import BaseModel
from typing import Optional

class OTPRequest(BaseModel):
    phone: str

class OTPVerify(BaseModel):
    phone: str
    otp: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str

class NodalOfficerLogin(BaseModel):
    email: str
    password: str

class AdminLogin(BaseModel):
    email: str
    password: str
