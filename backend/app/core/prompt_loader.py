from pathlib import Path

from app.core.exceptions import ConfigurationError


class PromptLoader:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> str:
        try:
            prompt = self.path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigurationError(
                "EVALUATION_PROMPT_MISSING",
                f"Evaluation prompt file was not found: {self.path}",
            ) from exc
        if not prompt:
            raise ConfigurationError(
                "EVALUATION_PROMPT_EMPTY",
                "Paste the road-design evaluation system prompt into the configured prompt file.",
            )
        return prompt

