"""Generate PostgreSQL StatefulSet and Service for an OrbitInstance."""

from __future__ import annotations

from orbit_operator.utils.labels import (
    resource_name,
    selector_labels,
    standard_labels,
)


def build_statefulset(name: str, namespace: str, spec: dict) -> dict:
    rname = resource_name(name, "db")
    pg_spec = spec.get("postgres", {})
    images = spec.get("images", {})
    image = images.get("postgres", "pgvector/pgvector:pg16")
    storage_size = pg_spec.get("storageSize", "10Gi")
    storage_class = pg_spec.get("storageClassName")

    labels = standard_labels("database", name)
    match_labels = selector_labels("database", name)
    secrets_name = resource_name(name, "secrets")

    pvc_spec: dict = {
        "accessModes": ["ReadWriteOnce"],
        "resources": {"requests": {"storage": storage_size}},
    }
    if storage_class:
        pvc_spec["storageClassName"] = storage_class

    return {
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "serviceName": rname,
            "replicas": 1,
            "selector": {"matchLabels": match_labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [
                        {
                            "name": "postgres",
                            "image": image,
                            "ports": [{"containerPort": 5432, "name": "postgres"}],
                            "env": [
                                {"name": "POSTGRES_USER", "value": "orbit"},
                                {
                                    "name": "POSTGRES_PASSWORD",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": secrets_name,
                                            "key": "db-password",
                                        }
                                    },
                                },
                                {"name": "POSTGRES_DB", "value": "orbit"},
                                {
                                    "name": "PGDATA",
                                    "value": "/var/lib/postgresql/data/pgdata",
                                },
                            ],
                            "volumeMounts": [
                                {
                                    "name": "data",
                                    "mountPath": "/var/lib/postgresql/data",
                                }
                            ],
                            "readinessProbe": {
                                "exec": {
                                    "command": [
                                        "pg_isready",
                                        "-U",
                                        "orbit",
                                        "-d",
                                        "orbit",
                                    ]
                                },
                                "initialDelaySeconds": 5,
                                "periodSeconds": 10,
                            },
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "256Mi"},
                                "limits": {"memory": "1Gi"},
                            },
                        }
                    ],
                },
            },
            "volumeClaimTemplates": [
                {
                    "metadata": {"name": "data"},
                    "spec": pvc_spec,
                }
            ],
        },
    }


def build_service(name: str, namespace: str) -> dict:
    rname = resource_name(name, "db")
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": standard_labels("database", name),
        },
        "spec": {
            "clusterIP": "None",
            "selector": selector_labels("database", name),
            "ports": [{"port": 5432, "targetPort": 5432, "name": "postgres"}],
        },
    }
