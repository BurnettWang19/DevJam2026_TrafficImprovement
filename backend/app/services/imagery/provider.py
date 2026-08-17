from dataclasses import dataclass


@dataclass(frozen=True)
class ImageryArtifact:
    data: bytes
    mime_type: str
    width: int
    height: int

