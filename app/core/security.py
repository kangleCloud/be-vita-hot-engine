"""Security helpers for bearer-token protected endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError

bearer_scheme = HTTPBearer(auto_error=False)


def verify_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    """Validate the internal bearer token."""

    expected_token = settings.hot_api_token.strip()
    if not credentials or credentials.scheme.lower() != "bearer" or not expected_token:
        raise UnauthorizedError()
    if credentials.credentials != expected_token:
        raise UnauthorizedError()
