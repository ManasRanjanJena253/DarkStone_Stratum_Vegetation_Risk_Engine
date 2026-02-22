import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Config():
    celery_url = os.getenv("REDIS_URL")
    user_db_url = os.getenv("DATABASE_URL")  # Contains user related data. Mainly two tables i.e. User details db and User requests logs from celery.
    analysis_db_url = os.getenv("ANALYSIS_DATABASE_URL")  # Contains all the data regarding our ml related analysis and processing.

settings = Config()