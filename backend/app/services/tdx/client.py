class TDXClient:
    """Boundary for future TDX enrichment of IntersectionScene data."""

    async def fetch_intersection_context(self, latitude: float, longitude: float) -> dict:
        raise NotImplementedError("TDX integration is planned for a later milestone.")
