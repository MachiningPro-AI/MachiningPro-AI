"""
Authentication for MachiningPro AI.

Two modes, selected automatically:

PILOT MODE  (MACHININGPRO_PILOT_USERS_FILE is set)
    Multi-user bcrypt credential store. Individual pilot accounts.
    Demo credentials (MACHININGPRO_DEV_USERNAME/PASSWORD) are NOT
    accepted in this mode.

DEV MODE  (fallback when MACHININGPRO_PILOT_USERS_FILE is not set)
    Single env-var credential for local development only.
    NOT suitable for production pilot access.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import jwt
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    display_name: str
    role: str
    expires_in: int


TOKEN_EXPIRE_MINUTES = 1440  # 24 hours for dev
JWT_SECRET_MIN_LENGTH = 32


def get_jwt_secret() -> str | None:
    """
    Load JWT signing secret from environment variable.

    Validates minimum length of 32 characters for security.

    Returns:
        JWT secret if configured and valid, None if not set or too short
        (auth fails closed)
    """
    secret = os.environ.get("MACHININGPRO_DEV_JWT_SECRET")
    if secret and len(secret) >= JWT_SECRET_MIN_LENGTH:
        return secret
    return None


def get_configured_credentials() -> dict | None:
    """
    Load local development credentials from environment variables.

    Returns:
        Dict with 'username', 'password', 'display_name', 'role' if configured
        None if environment variables are not set (auth fails closed)
    """
    username = os.environ.get("MACHININGPRO_DEV_USERNAME")
    password = os.environ.get("MACHININGPRO_DEV_PASSWORD")
    jwt_secret = get_jwt_secret()

    if not username or not password or not jwt_secret:
        # Any required auth configuration absent; fail closed
        return None

    return {
        "username": username,
        "password": password,
        "display_name": "MachiningPro AI Developer",
        "role": "engineer"  # Default role for local dev
    }


def authenticate(req: LoginRequest) -> LoginResponse | None:
    """
    Authenticate a login request.

    Pilot mode (MACHININGPRO_PILOT_USERS_FILE set):
        Looks up the user in the bcrypt credential store.
        Demo env-var credentials are NOT accepted.

    Dev mode (fallback):
        Validates against MACHININGPRO_DEV_USERNAME / MACHININGPRO_DEV_PASSWORD.

    Returns LoginResponse on success, None on any failure (fail-closed).
    Passwords are never logged.
    """
    from ..auth.pilot_users import (
        is_pilot_mode,
        lookup_pilot_user,
        verify_pilot_password,
    )

    jwt_secret = get_jwt_secret()
    if not jwt_secret:
        return None

    if is_pilot_mode():
        # --- Pilot mode: bcrypt credential store ---
        user = lookup_pilot_user(req.username)
        if user is None:
            return None
        if not user.active:
            return None
        if not verify_pilot_password(req.password, user.password_hash):
            return None

        expires = datetime.now(UTC) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
        payload = {"sub": req.username, "exp": expires, "role": user.role}
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")
        return LoginResponse(
            token=token,
            display_name=user.display_name,
            role=user.role,
            expires_in=TOKEN_EXPIRE_MINUTES * 60,
        )

    # --- Dev mode: env-var single credential ---
    creds = get_configured_credentials()
    if not creds:
        return None
    if req.username != creds["username"] or req.password != creds["password"]:
        return None

    expires = datetime.now(UTC) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": req.username, "exp": expires, "role": creds["role"]}
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    return LoginResponse(
        token=token,
        display_name=creds["display_name"],
        role=creds["role"],
        expires_in=TOKEN_EXPIRE_MINUTES * 60,
    )


def verify_token(token: str) -> dict | None:
    """
    Verify JWT token validity.

    Args:
        token: JWT token string

    Returns:
        Decoded payload if valid, None if expired or invalid
    """
    jwt_secret = get_jwt_secret()
    if not jwt_secret:
        # JWT secret not configured; can't verify
        return None

    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        return None
