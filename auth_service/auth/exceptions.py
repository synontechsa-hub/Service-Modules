class AuthError(Exception):
    """Base exception for all auth-related errors."""


class InvalidCredentialsError(AuthError):
    """Raised when username/password is incorrect."""


class AccountLockedError(AuthError):
    """Raised when an account is temporarily locked due to brute force protection."""


class AccountDisabledError(AuthError):
    """Raised when an account is disabled."""


class DuplicateUserError(AuthError):
    """Raised when a user with the same email or username already exists."""


class InvalidTokenError(AuthError):
    """Raised when an access or refresh token is invalid or has been replayed."""


class TokenExpiredError(AuthError):
    """Raised when a refresh token is expired."""
