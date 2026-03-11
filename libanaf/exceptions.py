class AnafException(Exception):
    """Base exception for libanaf."""

    pass


class AnafRequestError(AnafException):
    """Raised when an API request fails."""

    pass


class AuthorizationError(AnafException):
    """Raised when OAuth2 authorization is denied or fails."""

    pass
