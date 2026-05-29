"""
Custom application exceptions for clean error handling.
"""


class SyncVerseBaseException(Exception):
    """Base exception for all SyncVerse errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class EmployeeNotFoundException(SyncVerseBaseException):
    def __init__(self, employee_id: str):
        super().__init__(
            message=f"Employee with ID '{employee_id}' not found.",
            code="EMPLOYEE_NOT_FOUND",
        )


class TeamNotFoundException(SyncVerseBaseException):
    def __init__(self, team_id: str):
        super().__init__(
            message=f"Team with ID '{team_id}' not found.",
            code="TEAM_NOT_FOUND",
        )


class ModelNotLoadedException(SyncVerseBaseException):
    def __init__(self, model_name: str):
        super().__init__(
            message=f"ML model '{model_name}' is not loaded. Ensure training has been completed.",
            code="MODEL_NOT_LOADED",
        )


class InsufficientDataException(SyncVerseBaseException):
    def __init__(self, employee_id: str, missing: list):
        super().__init__(
            message=f"Insufficient data for employee '{employee_id}'. Missing: {', '.join(missing)}",
            code="INSUFFICIENT_DATA",
        )


class PredictionFailedException(SyncVerseBaseException):
    def __init__(self, detail: str):
        super().__init__(
            message=f"Prediction failed: {detail}",
            code="PREDICTION_FAILED",
        )


class DatabaseException(SyncVerseBaseException):
    def __init__(self, detail: str):
        super().__init__(
            message=f"Database error: {detail}",
            code="DATABASE_ERROR",
        )


class CacheException(SyncVerseBaseException):
    def __init__(self, detail: str):
        super().__init__(
            message=f"Cache error: {detail}",
            code="CACHE_ERROR",
        )
