import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Config(BaseSettings):   # BaseSettings will automatically fetch the env variables from .env,
                            # just the name of variables should be same as class variables (Not case sensitive)
    celery_url : str
    user_db_url : str      # Contains user related data. Mainly two tables i.e. User details db and User requests logs from celery.
    analysis_db_url : str  # Contains all the data regarding our ml related analysis and processing.

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Config()