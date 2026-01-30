from pydantic import BaseModel
import os

class Settings(BaseModel):
    DB_PATH: str = os.getenv("DB_PATH", "people_counter.db")
    APP_NAME: str = "people_counter_backend"

settings = Settings()
