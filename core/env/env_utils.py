from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, Field
from functools import lru_cache
from pathlib import Path
import re

class Settings(BaseSettings):
    ENV: str = 'dev'
    APP_NAME: str = 'hragent'
    DEBUG: bool = True
    MONGODB_URL: str
    DATABASE_NAME:str = None
    USER: str = None
    SECRET_KEY: str
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USER: str = None
    REDIS_PASSWORD: str = None

    # LLM Configuration
    LLM_TOKEN_LIMIT: int = 1000


    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    @field_validator("ENV")
    def validate_env(cls, v):
        allowed = {"dev", "staging", "prod"}
        if v not in allowed:
            raise ValueError(f"{v} should be one of the allowed in {allowed}")
        return v
    
    @property
    def is_production(self) -> bool:
        return self.ENV=="prod"
    
    @property
    def is_debuggable(self) -> bool:
        return self.ENV=="dev"
@lru_cache
def get_settings() -> Settings:
    return Settings()
        




