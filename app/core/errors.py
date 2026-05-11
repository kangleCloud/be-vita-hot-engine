"""Custom application errors."""

from __future__ import annotations

from typing import Any, Dict, Optional


class HotEngineError(Exception):
    """Base application error with HTTP metadata."""

    def __init__(
        self,
        error_code: str,
        detail: str,
        status_code: int,
        source_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(detail)
        self.error_code = error_code
        self.detail = detail
        self.status_code = status_code
        self.source_code = source_code
        self.extra = extra or {}


class UnauthorizedError(HotEngineError):
    """Raised when the request token is missing or invalid."""

    def __init__(self) -> None:
        super().__init__(
            error_code="unauthorized",
            detail="invalid or missing bearer token",
            status_code=401,
        )


class SourceNotFoundError(HotEngineError):
    """Raised when the requested source code is unsupported."""

    def __init__(self, source_code: str) -> None:
        super().__init__(
            error_code="source_not_found",
            detail="source not found: {0}".format(source_code),
            status_code=404,
            source_code=source_code,
        )


class UpstreamFetchError(HotEngineError):
    """Raised when an adapter cannot fetch or parse upstream data."""

    def __init__(self, source_code: str) -> None:
        super().__init__(
            error_code="upstream_fetch_failed",
            detail="failed to fetch source {0}".format(source_code),
            status_code=502,
            source_code=source_code,
        )
