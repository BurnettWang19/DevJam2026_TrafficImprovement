import json
from pathlib import Path
from typing import Any

from app.core.exceptions import ConfigurationError


class ClassicCaseRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def list(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigurationError(
                "CLASSIC_CASES_INVALID",
                f"Classic case data could not be loaded from {self.path}.",
            ) from exc

