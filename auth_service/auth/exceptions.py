class AuthError(Exception):
    """Base exception for all auth-related errors."""
    pass

class InvalidCredentialsError(AuthError):
    """Raised when username/password is incorrect."""
    pass

class AccountLockedError(AuthError):
    """Raised when an account is temporarily locked due to brute force protection."""
    pass

class AccountDisabledError(AuthError):
    """Raised when an account is disabled."""
    pass

class DuplicateUserError(AuthError):
    """Raised when a user with the same email or username already exists."""
    pass

class InvalidTokenError(AuthError):
    """Raised when a refresh token is invalid or has been replayed."""
    pass

class TokenExpiredError(AuthError):
    """Raised when a refresh token is expired."""
    pass
