"""Generate a Kubernetes Job that runs Alembic migrations on create or upgrade."""

from __future__ import annotations

import time

from orbit_operator.resources.configmap import db_url_env_vars, env_from_refs, secret_env_vars
from orbit_operator.utils.labels import resource_name, standard_labels

_TTL_AFTER_FINISHED = 300  # clean up completed Job after 5 minutes


def build_migration_job(
    name: str,
    namespace: str,
    spec: dict,
    *,
    suffix: str | None = None,
) -> dict:
    """Build a one-shot Job that runs ``alembic upgrade head``.

    A unique suffix is appended so the Job can be re-created on upgrades
    without conflicting with a previous run.
    """
    if suffix is None:
        suffix = str(int(time.time()))

    job_name = f"{resource_name(name, 'db-migrate')}-{suffix}"
    images = spec.get("images", {})
    image = images.get("backend", "quay.io/gshanmug-quay/orbit-backend:latest")
    secrets_name = resource_name(name, "secrets")
    db_svc = resource_name(name, "db")

    labels = standard_labels("migration", name)

    gcp_mounts: list[dict] = []
    gcp_volumes: list[dict] = []
    gcp = spec.get("gcp", {})
    sa_secret = gcp.get("serviceAccountSecret")
    if sa_secret:
        gcp_mounts = [
            {"name": "gcp-sa", "mountPath": "/var/run/secrets/gcp", "readOnly": True}
        ]
        gcp_volumes = [{"name": "gcp-sa", "secret": {"secretName": sa_secret}}]

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "ttlSecondsAfterFinished": _TTL_AFTER_FINISHED,
            "backoffLimit": 3,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "OnFailure",
                    "initContainers": [
                        {
                            "name": "wait-for-db",
                            "image": image,
                            "imagePullPolicy": "Always",
                            "command": [
                                "python",
                                "-c",
                                (
                                    "import socket, time, os\n"
                                    f"host = '{db_svc}'\n"
                                    "port = 5432\n"
                                    "for i in range(60):\n"
                                    "    try:\n"
                                    "        socket.create_connection((host, port), timeout=2)\n"
                                    "        print('DB is up'); break\n"
                                    "    except OSError:\n"
                                    "        print(f'Waiting for {{host}}:{{port}}...')\n"
                                    "        time.sleep(2)\n"
                                    "else:\n"
                                    "    raise RuntimeError('DB did not become ready')\n"
                                ),
                            ],
                        }
                    ],
                    "containers": [
                        {
                            "name": "migrate",
                            "image": image,
                            "imagePullPolicy": "Always",
                            "command": ["alembic", "upgrade", "head"],
                            "envFrom": env_from_refs(name),
                            "env": secret_env_vars(name) + db_url_env_vars(name),
                            "volumeMounts": gcp_mounts,
                        }
                    ],
                    "volumes": gcp_volumes,
                },
            },
        },
    }
