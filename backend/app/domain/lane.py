from dataclasses import dataclass


@dataclass(frozen=True)
class Lane:
    id: str
