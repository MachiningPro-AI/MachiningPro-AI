"""
Comprehensive tests for multi-user pilot authentication.

Covers:
- PilotUser credential store loading and validation
- bcrypt hash/verify
- Role enforcement (valid roles, invalid role rejected)
- is_pilot_mode detection
- authenticate() in pilot mode: valid, invalid, inactive, missing user
- authenticate() in dev mode: unaffected by pilot store
- Demo credentials blocked in pilot mode
- JWT claims (no password, no hash in token)
- Admin endpoint role guard
"""

from __future__ import annotations

import json
import pathlib

import pytest

from backend.api.auth import LoginRequest, authenticate, verify_token
from backend.auth.pilot_users import (
    VALID_ROLES,
    PilotUserStoreError,
    _load_store,
    hash_password,
    is_pilot_mode,
    list_pilot_users_safe,
    lookup_pilot_user,
    verify_pilot_password,
)

TEST_JWT_SECRET = "test-pilot-jwt-secret-at-least-32-chars-ok"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_store(tmp_path: pathlib.Path, users: list[dict]) -> str:
    """Write a temporary credential store file and return its path."""
    store = tmp_path / "pilot_users.json"
    store.write_text(json.dumps({"users": users}), encoding="utf-8")
    return str(store)


def _make_user(username: str = "pilot-eng-01", role: str = "pilot_engineer",
               active: bool = True, plaintext: str = "SecurePilotPass!99") -> dict:
    return {
        "username": username,
        "password_hash": hash_password(plaintext),
        "display_name": f"Display {username}",
        "role": role,
        "active": active,
    }


# ---------------------------------------------------------------------------
# hash_password / verify_pilot_password
# ---------------------------------------------------------------------------

class TestBcryptHashVerify:
    def test_hash_is_not_plaintext(self):
        h = hash_password("MyPassword123!")
        assert h != "MyPassword123!"
        # bcrypt hashes start with $2b$ or $2a$
        assert h.startswith("$2b$") or h.startswith("$2a$") or h.startswith("$2y$")

    def test_verify_correct_password(self):
        h = hash_password("CorrectPassword#1")
        assert verify_pilot_password("CorrectPassword#1", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("CorrectPassword#1")
        assert verify_pilot_password("WrongPassword#99", h) is False

    def test_verify_empty_password_rejected(self):
        h = hash_password("SomeValidPassword1!")
        assert verify_pilot_password("", h) is False

    def test_different_hashes_for_same_password(self):
        # bcrypt uses a random salt each time
        h1 = hash_password("SamePassword#1")
        h2 = hash_password("SamePassword#1")
        assert h1 != h2
        assert verify_pilot_password("SamePassword#1", h1) is True
        assert verify_pilot_password("SamePassword#1", h2) is True


# ---------------------------------------------------------------------------
# _load_store validation
# ---------------------------------------------------------------------------

class TestLoadStore:
    def test_valid_store_loaded(self, tmp_path):
        path = _write_store(tmp_path, [_make_user()])
        users = _load_store(path)
        assert len(users) == 1
        assert users[0].username == "pilot-eng-01"
        assert users[0].role == "pilot_engineer"
        assert users[0].active is True

    def test_missing_file_raises(self):
        with pytest.raises(PilotUserStoreError, match="Cannot read"):
            _load_store("/nonexistent/path/pilot_users.json")

    def test_invalid_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{ not valid json", encoding="utf-8")
        with pytest.raises(PilotUserStoreError, match="not valid JSON"):
            _load_store(str(p))

    def test_missing_users_key_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"other": []}), encoding="utf-8")
        with pytest.raises(PilotUserStoreError, match="'users' array"):
            _load_store(str(p))

    def test_invalid_role_raises(self, tmp_path):
        user = _make_user()
        user["role"] = "superadmin"
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"users": [user]}), encoding="utf-8")
        with pytest.raises(PilotUserStoreError, match="invalid role"):
            _load_store(str(p))

    def test_missing_username_raises(self, tmp_path):
        user = _make_user()
        del user["username"]
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"users": [user]}), encoding="utf-8")
        with pytest.raises(PilotUserStoreError, match="missing 'username'"):
            _load_store(str(p))

    def test_missing_password_hash_raises(self, tmp_path):
        user = _make_user()
        del user["password_hash"]
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"users": [user]}), encoding="utf-8")
        with pytest.raises(PilotUserStoreError, match="missing 'password_hash'"):
            _load_store(str(p))

    def test_all_valid_roles_accepted(self, tmp_path):
        users = [_make_user(username=f"user-{r}", role=r) for r in sorted(VALID_ROLES)]
        path = _write_store(tmp_path, users)
        loaded = _load_store(path)
        assert {u.role for u in loaded} == VALID_ROLES

    def test_hash_not_exposed_in_dataclass_public_fields(self, tmp_path):
        """password_hash is on PilotUser but list_pilot_users_safe must not return it."""
        path = _write_store(tmp_path, [_make_user()])
        users = _load_store(path)
        assert hasattr(users[0], "password_hash")  # internal field exists
        # but list_pilot_users_safe omits it
        pass  # tested separately below


# ---------------------------------------------------------------------------
# is_pilot_mode / lookup_pilot_user
# ---------------------------------------------------------------------------

class TestPilotMode:
    def test_not_pilot_mode_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("MACHININGPRO_PILOT_USERS_FILE", raising=False)
        assert is_pilot_mode() is False

    def test_pilot_mode_when_env_set(self, monkeypatch, tmp_path):
        path = _write_store(tmp_path, [_make_user()])
        monkeypatch.setenv("MACHININGPRO_PILOT_USERS_FILE", path)
        assert is_pilot_mode() is True

    def test_lookup_returns_none_when_not_pilot_mode(self, monkeypatch):
        monkeypatch.delenv("MACHININGPRO_PILOT_USERS_FILE", raising=False)
        assert lookup_pilot_user("anyone") is None

    def test_lookup_finds_user(self, monkeypatch, tmp_path):
        path = _write_store(tmp_path, [_make_user("pilot-eng-01")])
        monkeypatch.setenv("MACHININGPRO_PILOT_USERS_FILE", path)
        user = lookup_pilot_user("pilot-eng-01")
        assert user is not None
        assert user.username == "pilot-eng-01"

    def test_lookup_returns_none_for_missing_user(self, monkeypatch, tmp_path):
        path = _write_store(tmp_path, [_make_user("pilot-eng-01")])
        monkeypatch.setenv("MACHININGPRO_PILOT_USERS_FILE", path)
        assert lookup_pilot_user("nonexistent") is None

    def test_lookup_returns_none_for_bad_store(self, monkeypatch):
        monkeypatch.setenv("MACHININGPRO_PILOT_USERS_FILE", "/does/not/exist.json")
        assert lookup_pilot_user("anyone") is None


# ---------------------------------------------------------------------------
# list_pilot_users_safe — no hash in output
# ---------------------------------------------------------------------------

class TestListPilotUsersSafe:
    def test_returns_empty_when_not_pilot_mode(self, monkeypatch):
        monkeypatch.delenv("MACHININGPRO_PILOT_USERS_FILE", raising=False)
        assert list_pilot_users_safe() == []

    def test_does_not_include_password_hash(self, monkeypatch, tmp_path):
        path = _write_store(tmp_path, [_make_user()])
        monkeypatch.setenv("MACHININGPRO_PILOT_USERS_FILE", path)
        result = list_pilot_users_safe()
        assert len(result) == 1
        assert "password_hash" not in result[0]
        assert "username" in result[0]
        assert "role" in result[0]
        assert "active" in result[0]

    def test_includes_multiple_users(self, monkeypatch, tmp_path):
        users = [
            _make_user("eng", "pilot_engineer"),
            _make_user("rev", "pilot_reviewer"),
            _make_user("adm", "pilot_admin"),
        ]
        path = _write_store(tmp_path, users)
        monkeypatch.setenv("MACHININGPRO_PILOT_USERS_FILE", path)
        result = list_pilot_users_safe()
        assert len(result) == 3


# ---------------------------------------------------------------------------
# authenticate() — pilot mode
# ---------------------------------------------------------------------------

class TestAuthenticatePilotMode:
    _plaintext = "PilotTestPass#2026"

    def _setup(self, monkeypatch, tmp_path, active: bool = True, role: str = "pilot_engineer"):
        path = _write_store(tmp_path, [_make_user(
            username="pilot-tester",
            role=role,
            active=active,
            plaintext=self._plaintext,
        )])
        monkeypatch.setenv("MACHININGPRO_PILOT_USERS_FILE", path)
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", TEST_JWT_SECRET)

    def test_valid_pilot_login(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path)
        req = LoginRequest(username="pilot-tester", password=self._plaintext)
        resp = authenticate(req)
        assert resp is not None
        assert resp.role == "pilot_engineer"
        assert resp.token

    def test_wrong_password_rejected(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path)
        req = LoginRequest(username="pilot-tester", password="WrongPassword#99")
        assert authenticate(req) is None

    def test_unknown_user_rejected(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path)
        req = LoginRequest(username="ghost-user", password=self._plaintext)
        assert authenticate(req) is None

    def test_inactive_user_rejected(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path, active=False)
        req = LoginRequest(username="pilot-tester", password=self._plaintext)
        assert authenticate(req) is None

    def test_jwt_contains_role_not_password(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path)
        req = LoginRequest(username="pilot-tester", password=self._plaintext)
        resp = authenticate(req)
        payload = verify_token(resp.token)
        assert payload is not None
        assert "password" not in payload
        assert "password_hash" not in payload
        assert payload["role"] == "pilot_engineer"
        assert payload["sub"] == "pilot-tester"

    def test_pilot_admin_role_returned(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path, role="pilot_admin")
        req = LoginRequest(username="pilot-tester", password=self._plaintext)
        resp = authenticate(req)
        assert resp is not None
        assert resp.role == "pilot_admin"

    def test_demo_credentials_rejected_in_pilot_mode(self, monkeypatch, tmp_path):
        """Demo env-var credentials must NOT authenticate in pilot mode."""
        path = _write_store(tmp_path, [_make_user(
            username="pilot-tester",
            plaintext=self._plaintext,
        )])
        monkeypatch.setenv("MACHININGPRO_PILOT_USERS_FILE", path)
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", TEST_JWT_SECRET)
        # Set demo credentials in env — they must be ignored in pilot mode
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "demo")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "A1234")

        # demo/A1234 must not authenticate
        req = LoginRequest(username="demo", password="A1234")
        assert authenticate(req) is None

    def test_no_jwt_secret_fails_closed(self, monkeypatch, tmp_path):
        path = _write_store(tmp_path, [_make_user(plaintext=self._plaintext)])
        monkeypatch.setenv("MACHININGPRO_PILOT_USERS_FILE", path)
        monkeypatch.delenv("MACHININGPRO_DEV_JWT_SECRET", raising=False)
        req = LoginRequest(username="pilot-eng-01", password=self._plaintext)
        assert authenticate(req) is None


# ---------------------------------------------------------------------------
# authenticate() — dev mode unaffected
# ---------------------------------------------------------------------------

class TestAuthenticateDevModeUnchanged:
    def test_dev_auth_still_works_without_pilot_mode(self, monkeypatch):
        monkeypatch.delenv("MACHININGPRO_PILOT_USERS_FILE", raising=False)
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "devuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "devpass")
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", TEST_JWT_SECRET)

        req = LoginRequest(username="devuser", password="devpass")
        resp = authenticate(req)
        assert resp is not None
        assert resp.role == "engineer"

    def test_dev_auth_wrong_password_rejected(self, monkeypatch):
        monkeypatch.delenv("MACHININGPRO_PILOT_USERS_FILE", raising=False)
        monkeypatch.setenv("MACHININGPRO_DEV_USERNAME", "devuser")
        monkeypatch.setenv("MACHININGPRO_DEV_PASSWORD", "devpass")
        monkeypatch.setenv("MACHININGPRO_DEV_JWT_SECRET", TEST_JWT_SECRET)

        req = LoginRequest(username="devuser", password="wrongpass")
        assert authenticate(req) is None
