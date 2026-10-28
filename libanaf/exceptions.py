class AnafException(Exception):
    """Base exception for libanaf."""

    pass


class AnafRequestError(AnafException):
    """Raised when an API request fails."""

    pass


class AuthorizationError(AnafException):
    """Raised when OAuth2 authorization is denied or fails."""

    pass


class TokenExpiredError(AuthorizationError):
    """Raised when both the access token and refresh token are expired.

    This signals that a hard re-authorization (``libanaf auth``) is required
    because the refresh token can no longer be used to obtain a new access token.
    """

    pass


class SpvSessionError(AuthorizationError):
    """Raised when the SPV session is missing or ANAF bounced the request to the certificate login.

    A new session must be bootstrapped with the qualified certificate (e.g. in a browser
    with vToken) and its cookies imported again via ``libanaf spv import-cookies``.
    """

    pass
