"""Formal login and signed Bearer-token validation without plaintext secrets."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any
from uuid import uuid4

from fastapi import Header, HTTPException

from .core.config import get_settings
from .services.project_registry import DEFAULT_ACTOR_ID


class AuthError(ValueError):
    """Raised when authentication configuration or a token is invalid."""


@dataclass(frozen=True)
class AuthUser:
    username: str
    actor_id: str
    password_hash: str


@dataclass(frozen=True)
class AuthToken:
    username: str
    actor_id: str
    issued_at: int
    expires_at: int


def hash_password(password: str, *, iterations: int = 310_000) -> str:
    if not password or len(password) > 512:
        raise AuthError("password length is invalid")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(iterations, _encode(salt), _encode(digest))


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(raw_iterations)
        salt = _decode(raw_salt)
        expected = _decode(raw_digest)
    except (ValueError, TypeError):
        return False
    if not 100_000 <= iterations <= 2_000_000 or not salt or not expected:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def load_users(project_root: str | Path) -> tuple[AuthUser, ...]:
    path_value = get_settings().auth_users_file
    if not path_value:
        raise AuthError("DEVSAGE_AUTH_USERS_FILE must be configured")
    path = Path(path_value).expanduser()
    if path.is_absolute():
        resolved = path.resolve()
    else:
        root = Path(project_root).expanduser().resolve()
        resolved = (root / path).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise AuthError("auth users file must stay inside the project root") from exc
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthError("auth users file could not be loaded") from exc
    raw_users = payload.get("users") if isinstance(payload, dict) else None
    if not isinstance(raw_users, list) or not raw_users:
        raise AuthError("auth users file must contain a non-empty users list")
    users: list[AuthUser] = []
    seen: set[str] = set()
    for item in raw_users:
        if not isinstance(item, dict):
            raise AuthError("auth users file contains an invalid user")
        username = str(item.get("username", "")).strip()
        actor_id = str(item.get("actor_id", "")).strip()
        password_hash = str(item.get("password_hash", "")).strip()
        if not username or username in seen or not actor_id:
            raise AuthError("auth users file contains duplicate or empty identity")
        if not _looks_like_password_hash(password_hash):
            raise AuthError("auth users file contains an invalid password hash")
        seen.add(username)
        users.append(AuthUser(username, actor_id, password_hash))
    return tuple(users)


def authenticate(username: str, password: str, project_root: str | Path) -> AuthUser:
    clean_username = username.strip()
    if not clean_username or not password:
        raise AuthError("invalid credentials")
    for user in load_users(project_root):
        if hmac.compare_digest(user.username, clean_username) and verify_password(
            password, user.password_hash
        ):
            return user
    raise AuthError("invalid credentials")


def issue_token(user: AuthUser) -> tuple[str, int]:
    settings = get_settings()
    secret = _auth_secret()
    ttl = settings.auth_token_ttl_seconds
    if not 60 <= ttl <= 86_400:
        raise AuthError("DEVSAGE_AUTH_TOKEN_TTL must be between 60 and 86400 seconds")
    now = int(time.time())
    payload = {
        "sub": user.username,
        "actor_id": user.actor_id,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid4().hex,
    }
    encoded_header = _json_part({"alg": "HS256", "typ": "DevSage"})
    encoded_payload = _json_part(payload)
    unsigned = f"{encoded_header}.{encoded_payload}"
    signature = _sign(unsigned, secret)
    return f"{unsigned}.{signature}", ttl


def decode_token(token: str) -> AuthToken:
    try:
        encoded_header, encoded_payload, signature = token.split(".", 2)
        header = json.loads(_decode_text(encoded_header))
        payload = json.loads(_decode_text(encoded_payload))
        if header != {"alg": "HS256", "typ": "DevSage"}:
            raise AuthError("invalid bearer token")
        expected = _sign(f"{encoded_header}.{encoded_payload}", _auth_secret())
        if not hmac.compare_digest(signature, expected):
            raise AuthError("invalid bearer token")
        username = str(payload["sub"])
        actor_id = str(payload["actor_id"])
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
    except (AuthError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise AuthError("invalid bearer token") from None
    if not username or not actor_id or expires_at <= int(time.time()) or issued_at > expires_at:
        raise AuthError("bearer token is expired or invalid")
    return AuthToken(username, actor_id, issued_at, expires_at)


def resolve_actor_id(
    authorization: str | None = Header(default=None),
    legacy_actor_id: str | None = Header(default=None, alias="X-DevSage-Actor"),
) -> str:
    """Use signed auth when enabled, otherwise keep local-demo compatibility."""

    if not get_settings().auth_enabled:
        return (legacy_actor_id or DEFAULT_ACTOR_ID).strip() or DEFAULT_ACTOR_ID
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer authentication is required")
    try:
        token = decode_token(authorization[7:].strip())
    except AuthError:
        raise HTTPException(status_code=401, detail="Bearer authentication is invalid") from None
    if legacy_actor_id and legacy_actor_id.strip() != token.actor_id:
        raise HTTPException(status_code=403, detail="actor header does not match authenticated identity")
    return token.actor_id


def _auth_secret() -> str:
    settings = get_settings()
    secret = os.getenv(settings.auth_secret_env, "").strip()
    if len(secret) < 32:
        raise AuthError("authentication secret must be at least 32 characters")
    return secret


def _looks_like_password_hash(value: str) -> bool:
    parts = value.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
        return 100_000 <= iterations <= 2_000_000 and bool(_decode(parts[2])) and bool(_decode(parts[3]))
    except (ValueError, TypeError):
        return False


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _decode_text(value: str) -> str:
    return _decode(value).decode("utf-8")


def _json_part(value: dict[str, Any]) -> str:
    return _encode(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _sign(value: str, secret: str) -> str:
    return _encode(hmac.new(secret.encode("utf-8"), value.encode("ascii"), hashlib.sha256).digest())
