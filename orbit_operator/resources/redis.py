"""Generate Redis Deployment and Service for an OrbitInstance."""

from __future__ import annotations

from orbit_operator.utils.labels import (
    resource_name,
    selector_labels,
    standard_labels,
)


def build_deployment(name: str, namespace: str, spec: dict) -> dict:
    rname = resource_name(name, "redis")
    redis_spec = spec.get("redis", {})
    images = spec.get("images", {})
    image = images.get("redis", "redis:7-alpine")
    mem_limit = redis_spec.get("memoryLimit", "256Mi")

    labels = standard_labels("cache", name)
    match_labels = selector_labels("cache", name)

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": match_labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [
                        {
                            "name": "redis",
                            "image": image,
                            "ports": [{"containerPort": 6379, "name": "redis"}],
                            "readinessProbe": {
                                "exec": {"command": ["redis-cli", "ping"]},
                                "initialDelaySeconds": 3,
                                "periodSeconds": 5,
                            },
                            "resources": {
                                "requests": {"cpu": "50m", "memory": "64Mi"},
                                "limits": {"memory": mem_limit},
                            },
                        }
                    ]
                },
            },
        },
    }


def build_service(name: str, namespace: str) -> dict:
    rname = resource_name(name, "redis")
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": standard_labels("cache", name),
        },
        "spec": {
            "selector": selector_labels("cache", name),
            "ports": [{"port": 6379, "targetPort": 6379, "name": "redis"}],
        },
    }
