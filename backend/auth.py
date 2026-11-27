"""Zero-dependency PBKDF2 password hashing, HS256 JWT tokens, and Multi-Tenant RBAC."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Optional

from fastapi import Header, HTTPException


JWT_SECRET = os.getenv("PANELCRAFT_JWT_SECRET", "panelcraft-dev-jwt-secret-change-in-prod")
JWT_EXPIRY_SEC = int(os.getenv("PANELCRAFT_JWT_EXPIRY_SEC", str(60 * 60 * 24 * 7)))

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"read", "edit_project", "manage_catalog", "create_revision", "release_revision", "rollback_revision", "manage_org", "manage_settings"},
    "reviewer": {"read", "edit_project", "manage_catalog", "create_revision", "release_revision", "rollback_revision"},
    "designer": {"read", "edit_project", "manage_catalog", "create_revision"},
    "viewer": {"read"},
}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, salt, hex_dk = stored_hash.split("$", 2)
        if scheme != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
        return hmac.compare_digest(dk.hex(), hex_dk)
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * ((4 - len(segment) % 4) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def create_access_token(user_id: str, email: str, full_name: str, role: str, tenant_id: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "name": full_name,
        "role": role,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + JWT_EXPIRY_SEC,
    }
    h_seg = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_seg = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(JWT_SECRET.encode("utf-8"), f"{h_seg}.{p_seg}".encode("ascii"), hashlib.sha256).digest()
    return f"{h_seg}.{p_seg}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token")
        h_seg, p_seg, s_seg = parts
        expected_sig = hmac.new(
            JWT_SECRET.encode("utf-8"),
            f"{h_seg}.{p_seg}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        actual_sig = _b64url_decode(s_seg)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid signature")
        payload = json.loads(_b64url_decode(p_seg).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Token expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired auth token: {exc}") from exc


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict[str, Any]]:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return decode_access_token(authorization[7:].strip())
    return None


def enforce_permission(user: Optional[dict[str, Any]], permission: str) -> str:
    """Enforce RBAC if authenticated (or if PANELCRAFT_AUTH_REQUIRED=true). Returns actor label."""
    auth_required = os.getenv("PANELCRAFT_AUTH_REQUIRED", "false").lower() == "true"
    if user is None:
        if auth_required:
            raise HTTPException(status_code=401, detail="Authentication required.")
        return "Guest Admin (demo)"

    role = str(user.get("role", "viewer"))
    if not has_permission(role, permission):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: role '{role}' lacks '{permission}'.",
        )
    return f"{user.get('name', user.get('email', 'User'))} ({role})"
