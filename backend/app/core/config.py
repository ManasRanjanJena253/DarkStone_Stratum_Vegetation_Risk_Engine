import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Config(BaseSettings):
    celery_url: str
    user_db_url: str
    analysis_db_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    sentinel_api_key: str = ""
    opentopo_api_key: str = ""

    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_individual: str
    stripe_price_entrepreneurial: str
    stripe_price_government: str

    risk_threshold_meters: float = 3.0
    max_requests_free: int = 5
    max_requests_individual: int = 100
    max_requests_entrepreneurial: int = 1000
    max_requests_government: int = -1

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Config()

PLAN_REQUEST_LIMITS = {
    "Free": settings.max_requests_free,
    "Individual": settings.max_requests_individual,
    "Entrepreneurial": settings.max_requests_entrepreneurial,
    "Government": settings.max_requests_government,
}

STRIPE_PRICE_MAP = {
    "Individual": settings.stripe_price_individual,
    "Entrepreneurial": settings.stripe_price_entrepreneurial,
    "Government": settings.stripe_price_government,
}