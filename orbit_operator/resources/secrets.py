"""Generate Kubernetes Secrets for an OrbitInstance."""

from __future__ import annotations

import base64
import secrets as stdlib_secrets

from orbit_operator.utils.labels import resource_name, standard_labels

_PASSWORD_LENGTH = 24


def _random_cookie_secret() -> str:
    """Return a base64 string that is exactly 32 bytes long.

    oauth-proxy requires the cookie-secret file to be exactly 16, 24, or 32
    bytes when --pass-access-token=true. base64(24 raw bytes) = 32 chars.
    """
    return base64.b64encode(stdlib_secrets.token_bytes(24)).decode()


def _random_password(length: int = _PASSWORD_LENGTH) -> str:
    return stdlib_secrets.token_urlsafe(length)


def build_app_secret(
    name: str,
    namespace: str,
    *,
    existing_data: dict[str, str] | None = None,
) -> dict:
    """Build the orbit-secrets Secret. Preserves existing values on update."""
    rname = resource_name(name, "secrets")
    data = existing_data or {}

    if "db-password" not in data:
        data["db-password"] = _random_password()
    if "secret-key" not in data:
        data["secret-key"] = _random_password(32)
    if "cookie-secret" not in data:
        data["cookie-secret"] = _random_cookie_secret()

    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": standard_labels("secrets", name),
        },
        "type": "Opaque",
        "stringData": data,
    }
