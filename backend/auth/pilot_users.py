"""
Minimal pilot-user credential store for MachiningPro AI production pilot.

Activated when MACHININGPRO_PILOT_USERS_FILE env var points to a JSON
credential file.  That file is NOT committed to source control.

See backend/auth/pilot_users.json.example for the expected schema.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import bcrypt as _bcrypt

VALID_ROLES: frozenset[str] = frozenset({"pilot_engineer", "pilot_reviewer", "pilot_admin"})

_BCRYPT_ROUNDS = 12


@dataclass(frozen=True)
class PilotUser:
    username: str
    password_hash: str
    display_name: str
    role: str
    active: bool


class PilotUserStoreError(Exception):
    """Raised when the credential store cannot be loaded or is malformed."""


def _load_store(path: str) -> list[PilotUser]:
    """
    Parse the JSON credential store.  Raises PilotUserStoreError on any
    structural problem so callers can fail closed rather than silently.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise PilotUserStoreError(f"Cannot read credential store: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PilotUserStoreError(f"Credential store is not valid JSON: {exc}") from exc

    if not isinstance(data, dict) or "users" not in data:
        raise PilotUserStoreError("Credential store must be a JSON object with a 'users' array")

    users: list[PilotUser] = []
    for rec in data["users"]:
        username = rec.get("username", "").strip()
        password_hash = rec.get("password_hash", "").strip()
        role = rec.get("role", "").strip()

        if not username:
            raise PilotUserStoreError("User record missing 'username'")
        if not password_hash:
            raise PilotUserStoreError(f"User '{username}' missing 'password_hash'")
        if role not in VALID_ROLES:
            raise PilotUserStoreError(
                f"User '{username}' has invalid role '{role}'. "
                f"Valid roles: {sorted(VALID_ROLES)}"
            )

        users.append(PilotUser(
            username=username,
            password_hash=password_hash,
            display_name=rec.get("display_name", username),
            role=role,
            active=bool(rec.get("active", True)),
        ))

    return users


def get_pilot_users_file() -> str | None:
    """Return the path to the credential store, or None if not configured."""
    return os.environ.get("MACHININGPRO_PILOT_USERS_FILE") or None


def is_pilot_mode() -> bool:
    """Return True when the pilot credential store is configured."""
    return get_pilot_users_file() is not None


def lookup_pilot_user(username: str) -> PilotUser | None:
    """
    Look up a user in the credential store by username.

    Returns None when:
    - pilot mode is not active
    - the credential store cannot be read
    - no user with that username exists
    """
    path = get_pilot_users_file()
    if not path:
        return None
    try:
        users = _load_store(path)
    except PilotUserStoreError:
        return None
    for user in users:
        if user.username == username:
            return user
    return None


def verify_pilot_password(plaintext: str, stored_hash: str) -> bool:
    """Constant-time bcrypt verification. Never logs the plaintext password."""
    try:
        return _bcrypt.checkpw(plaintext.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False


def hash_password(plaintext: str) -> str:
    """Generate a bcrypt hash (cost factor 12) suitable for storage in the credential file."""
    salt = _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return _bcrypt.hashpw(plaintext.encode("utf-8"), salt).decode("utf-8")


def list_pilot_users_safe() -> list[dict]:
    """
    Admin-only listing.  Returns user metadata WITHOUT password hashes.
    Safe to include in API responses.
    """
    path = get_pilot_users_file()
    if not path:
        return []
    try:
        users = _load_store(path)
    except PilotUserStoreError:
        return []
    return [
        {
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "active": u.active,
        }
        for u in users
    ]
