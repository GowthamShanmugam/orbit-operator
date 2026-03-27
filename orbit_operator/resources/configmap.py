"""Generate the ConfigMap that holds non-secret app configuration."""

from __future__ import annotations

from orbit_operator.utils.labels import resource_name, standard_labels


def build_configmap(name: str, namespace: str, spec: dict) -> dict:
    """Build the orbit-config ConfigMap from the CR spec."""
    rname = resource_name(name, "config")
    db_svc = resource_name(name, "db")
    redis_svc = resource_name(name, "redis")

    ai = spec.get("ai", {})
    provider = ai.get("provider", "vertex")

    data = {
        "REDIS_URL": f"redis://{redis_svc}:6379/0",
        "CLAUDE_PROVIDER": provider,
        "CLAUDE_DEFAULT_MODEL": ai.get("defaultModel", "claude-sonnet-4-20250514"),
        "CORS_ORIGINS": "*",
    }

    if provider == "vertex":
        data["GCP_PROJECT_ID"] = ai.get("vertexProjectId", "")
        data["GCP_REGION"] = ai.get("vertexRegion", "us-east5")

    gcp = spec.get("gcp", {})
    if gcp.get("serviceAccountSecret"):
        data["GOOGLE_APPLICATION_CREDENTIALS"] = "/var/run/secrets/gcp/sa-key.json"

    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": standard_labels("config", name),
        },
        "data": data,
    }


def env_from_refs(name: str) -> list[dict]:
    """Return envFrom entries that combine the ConfigMap and Secret."""
    return [
        {"configMapRef": {"name": resource_name(name, "config")}},
    ]


def secret_env_vars(name: str) -> list[dict]:
    """Return individual env vars sourced from the app Secret."""
    secrets_name = resource_name(name, "secrets")
    return [
        {
            "name": "SECRET_KEY",
            "valueFrom": {"secretKeyRef": {"name": secrets_name, "key": "secret-key"}},
        },
        {
            "name": "DB_PASSWORD",
            "valueFrom": {"secretKeyRef": {"name": secrets_name, "key": "db-password"}},
        },
    ]


def db_url_env_vars(name: str) -> list[dict]:
    """Return DATABASE_URL env entries that use Kubernetes $(VAR) expansion.

    These MUST be defined as explicit env entries (not in a ConfigMap) because
    Kubernetes only performs $(VAR) substitution in env[].value fields.
    DB_PASSWORD must appear earlier in the env list (via secret_env_vars).
    """
    db_svc = resource_name(name, "db")
    return [
        {
            "name": "DATABASE_URL",
            "value": f"postgresql+asyncpg://orbit:$(DB_PASSWORD)@{db_svc}:5432/orbit",
        },
        {
            "name": "DATABASE_URL_SYNC",
            "value": f"postgresql://orbit:$(DB_PASSWORD)@{db_svc}:5432/orbit",
        },
    ]
