from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_anon_key: str = ""
    anthropic_api_key: str = ""
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    redis_url: str = ""
    otp_ttl_seconds: int = 600
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
