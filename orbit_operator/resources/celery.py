"""Generate Celery Worker Deployment for an OrbitInstance."""

from __future__ import annotations

from orbit_operator.resources.configmap import env_from_refs, secret_env_vars
from orbit_operator.utils.labels import (
    resource_name,
    selector_labels,
    standard_labels,
)


def _gcp_volume_mounts(spec: dict) -> list[dict]:
    gcp = spec.get("gcp", {})
    if not gcp.get("serviceAccountSecret"):
        return []
    return [{"name": "gcp-sa", "mountPath": "/var/run/secrets/gcp", "readOnly": True}]


def _gcp_volumes(spec: dict) -> list[dict]:
    gcp = spec.get("gcp", {})
    secret_name = gcp.get("serviceAccountSecret")
    if not secret_name:
        return []
    return [{"name": "gcp-sa", "secret": {"secretName": secret_name}}]


def build_deployment(name: str, namespace: str, spec: dict) -> dict:
    rname = resource_name(name, "celery")
    images = spec.get("images", {})
    image = images.get("backend", "quay.io/gshanmug-quay/orbit-backend:latest")
    replicas = spec.get("celeryWorker", {}).get("replicas", 1)

    labels = standard_labels("worker", name)
    match_labels = selector_labels("worker", name)

    container: dict = {
        "name": "celery",
        "image": image,
        "imagePullPolicy": "Always",
        "command": ["celery", "-A", "app.workers", "worker", "-l", "info"],
        "envFrom": env_from_refs(name),
        "env": secret_env_vars(name),
        "volumeMounts": _gcp_volume_mounts(spec),
        "resources": {
            "requests": {"cpu": "100m", "memory": "256Mi"},
            "limits": {"memory": "1Gi"},
        },
    }

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": match_labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [container],
                    "volumes": _gcp_volumes(spec),
                },
            },
        },
    }
