from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Road Intersection AI"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_fallback_url: str = "https://overpass.private.coffee/api/interpreter"
    osm_timeout_seconds: float = 25.0
    gemini_api_key: str = ""
    gemini_vision_model: str = "gemini-3.5-flash"
    gemini_reasoning_model: str = "gemini-3.5-flash"
    gemini_image_model: str = "gemini-3.1-flash-image"
    gemini_timeout_seconds: float = 90.0
    google_maps_api_key: str = ""
    imagery_width: int = 640
    imagery_height: int = 640
    imagery_scale: int = 2
    evaluation_prompt_path: Path = Path("prompts/intersection_evaluation_system_prompt.md")
    classic_cases_path: Path = Path("classic_cases/cases.json")
    max_classic_case_matches: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
