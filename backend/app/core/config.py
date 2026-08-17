from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Road Intersection AI"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    osm_timeout_seconds: float = 25.0

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
