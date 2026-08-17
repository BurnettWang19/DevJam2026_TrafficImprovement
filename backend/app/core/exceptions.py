class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class OSMAPIError(AppError):
    def __init__(self, message: str = "OpenStreetMap data request failed") -> None:
        super().__init__("OSM_API_FAILURE", message, 502)


class NoRoadDataFoundError(AppError):
    def __init__(self) -> None:
        super().__init__("NO_ROAD_DATA_FOUND", "No nearby OSM road data was found", 404)


class ConfigurationError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 503)


class ExternalServiceError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 502)


class ModelOutputError(AppError):
    def __init__(self, message: str = "Gemini returned an invalid structured response") -> None:
        super().__init__("MODEL_OUTPUT_INVALID", message, 502)
