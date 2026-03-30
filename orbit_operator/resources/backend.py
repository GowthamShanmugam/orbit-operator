"""Generate Backend (FastAPI) Deployment and Service for an OrbitInstance."""

from __future__ import annotations

from orbit_operator.resources.configmap import db_url_env_vars, env_from_refs, secret_env_vars
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


def _anthropic_env(spec: dict) -> list[dict]:
    ai = spec.get("ai", {})
    ref = ai.get("anthropicApiKeySecret")
    if not ref or ai.get("provider") != "anthropic":
        return []
    return [
        {
            "name": "ANTHROPIC_API_KEY",
            "valueFrom": {
                "secretKeyRef": {
                    "name": ref["secretRef"],
                    "key": ref.get("key", "api-key"),
                }
            },
        }
    ]


def build_pvc(name: str, namespace: str, spec: dict) -> dict:
    """Build a PersistentVolumeClaim for backend data (repos, caches, etc.)."""
    rname = resource_name(name, "backend-data")
    backend_spec = spec.get("backend", {})
    storage = backend_spec.get("dataVolumeSize", "10Gi")
    storage_class = backend_spec.get("storageClassName")

    pvc: dict = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": standard_labels("backend", name),
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": storage}},
        },
    }
    if storage_class:
        pvc["spec"]["storageClassName"] = storage_class
    return pvc


def build_deployment(name: str, namespace: str, spec: dict) -> dict:
    rname = resource_name(name, "backend")
    pvc_name = resource_name(name, "backend-data")
    images = spec.get("images", {})
    image = images.get("backend", "quay.io/gshanmug-quay/orbit-backend:latest")
    replicas = spec.get("backend", {}).get("replicas", 1)

    labels = standard_labels("backend", name)
    match_labels = selector_labels("backend", name)

    container: dict = {
        "name": "backend",
        "image": image,
        "imagePullPolicy": "Always",
        "ports": [{"containerPort": 8000, "name": "http"}],
        "envFrom": env_from_refs(name),
        "env": secret_env_vars(name) + db_url_env_vars(name) + _anthropic_env(spec),
        "volumeMounts": [
            {"name": "data", "mountPath": "/app/data"},
        ] + _gcp_volume_mounts(spec),
        "readinessProbe": {
            "httpGet": {"path": "/health", "port": 8000},
            "initialDelaySeconds": 10,
            "periodSeconds": 10,
        },
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"memory": "2Gi"},
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
            "strategy": {"type": "Recreate"},
            "selector": {"matchLabels": match_labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [container],
                    "volumes": [
                        {
                            "name": "data",
                            "persistentVolumeClaim": {"claimName": pvc_name},
                        },
                    ] + _gcp_volumes(spec),
                },
            },
        },
    }


def build_service(name: str, namespace: str) -> dict:
    rname = resource_name(name, "backend")
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": standard_labels("backend", name),
        },
        "spec": {
            "selector": selector_labels("backend", name),
            "ports": [{"port": 8000, "targetPort": 8000, "name": "http"}],
        },
    }
