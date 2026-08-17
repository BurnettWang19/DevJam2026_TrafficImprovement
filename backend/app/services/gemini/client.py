import asyncio

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import ConfigurationError, ExternalServiceError, ModelOutputError


class GeminiClient:
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY_MISSING",
                "Set GEMINI_API_KEY in backend/.env before running the analysis pipeline.",
            )
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def structured(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: type[BaseModel],
        system_instruction: str | None = None,
        image: bytes | None = None,
        image_mime_type: str = "image/png",
    ) -> BaseModel:
        contents: list[object] = [prompt]
        if image is not None:
            contents.append(types.Part.from_bytes(data=image, mime_type=image_mime_type))

        def call() -> BaseModel:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=response_schema,
                    ),
                )
                if response.parsed is not None:
                    return response.parsed
                return response_schema.model_validate_json(response.text)
            except ValidationError as exc:
                raise ModelOutputError() from exc
            except Exception as exc:
                raise ExternalServiceError(
                    "GEMINI_REQUEST_FAILED",
                    f"Gemini model request failed for {model}.",
                ) from exc

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(call),
                timeout=settings.gemini_timeout_seconds,
            )
        except TimeoutError as exc:
            raise ExternalServiceError(
                "GEMINI_TIMEOUT",
                f"Gemini model {model} did not respond before the configured timeout.",
            ) from exc

    async def generate_image(self, *, prompt: str, source_image: bytes) -> tuple[bytes, str]:
        def call() -> tuple[bytes, str]:
            try:
                response = self.client.models.generate_content(
                    model=settings.gemini_image_model,
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=source_image, mime_type="image/png"),
                    ],
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
                )
                for part in response.parts:
                    if part.inline_data is not None and part.inline_data.data:
                        return part.inline_data.data, part.inline_data.mime_type or "image/png"
            except Exception as exc:
                raise ExternalServiceError(
                    "IMAGE_GENERATION_FAILED",
                    f"Image generation failed for {settings.gemini_image_model}.",
                ) from exc
            raise ExternalServiceError(
                "IMAGE_GENERATION_FAILED",
                "The image model returned no image.",
            )

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(call),
                timeout=settings.gemini_timeout_seconds,
            )
        except TimeoutError as exc:
            raise ExternalServiceError(
                "GEMINI_TIMEOUT",
                f"Gemini image model {settings.gemini_image_model} timed out.",
            ) from exc
