"""Custom exceptions for bilibili-cli."""


class BiliError(Exception):
    """Base exception for bilibili-cli errors."""


class InvalidBvidError(BiliError):
    """Raised when a BV ID cannot be parsed or is malformed."""


class NetworkError(BiliError):
    """Raised when upstream network/API requests fail."""


class AuthenticationError(BiliError):
    """Raised when authentication data is missing or invalid."""


class RateLimitError(BiliError):
    """Raised when Bilibili rate-limits the request (HTTP 412/429)."""


class NotFoundError(BiliError):
    """Raised when a video, user, or resource is not found."""
