class AnafException(Exception):
    """Base exception for libanaf."""

    pass


class AnafRequestError(AnafException):
    """Raised when an API request fails."""

    pass
