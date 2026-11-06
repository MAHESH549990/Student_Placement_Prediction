class StorageUnavailable(RuntimeError):
    """Raised when configured persistent storage cannot be reached."""


class ValidationError(ValueError):
    """Raised for invalid user supplied data."""
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code
