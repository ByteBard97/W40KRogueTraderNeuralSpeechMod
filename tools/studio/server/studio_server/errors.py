class ApiError(Exception):
    """Raised by handlers; the router turns it into {"error": message} with this HTTP status."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message
