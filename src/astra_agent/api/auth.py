"""API authentication and authorization guards."""

from __future__ import annotations

from typing import Optional
from fastapi import Header, HTTPException, status
from astra_agent.core.config import settings


async def verify_api_key(authorization: Optional[str] = Header(None)) -> bool:
    """Verifies Bearer token if ASTRA_API_AUTH_TOKEN is configured."""
    expected_token = settings.api_auth_token
    if not expected_token:
        # If no token configured, allow access (default local development)
        return True

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication token.",
        )

    return True
