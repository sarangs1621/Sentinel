class SentinelError(Exception):
    """Base class for all domain-level errors raised by the service layer."""


class NotFoundError(SentinelError):
    """Raised when a requested resource does not exist."""


class ConflictError(SentinelError):
    """Raised when an operation would violate a uniqueness constraint."""


class AuthenticationError(SentinelError):
    """Raised for invalid credentials or invalid/expired tokens."""


class PermissionDeniedError(SentinelError):
    """Raised when an authenticated user lacks permission for an action."""


class ValidationError(SentinelError):
    """Raised when input data is well-formed but semantically invalid."""


class AccountLockedError(SentinelError):
    """Raised when login is blocked due to too many recent failed attempts."""
