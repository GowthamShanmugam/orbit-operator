"""Handler for OrbitInstance creation -- provisions all child resources."""

from __future__ import annotations

import base64
import hashlib
import json
import logging

import kopf
import kubernetes

from orbit_operator.resources import (
    auth,
    backend,
    configmap,
    frontend,
    migration,
    postgres,
    redis,
    route,
    secrets,
)
from orbit_operator.utils.labels import resource_name

logger = logging.getLogger(__name__)

CRD_GROUP = "orbit.redhat.com"
CRD_VERSION = "v1alpha1"
CRD_PLURAL = "orbitinstances"


def _apply(api: kubernetes.client.ApiClient, resource: dict, namespace: str) -> None:
    """Server-side apply a single resource dict."""
    kind = resource["kind"]
    name = resource["metadata"]["name"]
    api_version = resource.get("apiVersion", "v1")

    if kind == "Secret":
        v1 = kubernetes.client.CoreV1Api(api)
        try:
            v1.read_namespaced_secret(name, namespace)
            v1.patch_namespaced_secret(name, namespace, resource)
            logger.info("Updated Secret %s", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                v1.create_namespaced_secret(namespace, resource)
                logger.info("Created Secret %s", name)
            else:
                raise

    elif kind == "ConfigMap":
        v1 = kubernetes.client.CoreV1Api(api)
        try:
            v1.read_namespaced_config_map(name, namespace)
            v1.patch_namespaced_config_map(name, namespace, resource)
            logger.info("Updated ConfigMap %s", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                v1.create_namespaced_config_map(namespace, resource)
                logger.info("Created ConfigMap %s", name)
            else:
                raise

    elif kind == "PersistentVolumeClaim":
        v1 = kubernetes.client.CoreV1Api(api)
        try:
            v1.read_namespaced_persistent_volume_claim(name, namespace)
            logger.info("PVC %s already exists, skipping (immutable)", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                v1.create_namespaced_persistent_volume_claim(namespace, resource)
                logger.info("Created PVC %s", name)
            else:
                raise

    elif kind == "Service":
        v1 = kubernetes.client.CoreV1Api(api)
        try:
            existing = v1.read_namespaced_service(name, namespace)
            resource["metadata"]["resourceVersion"] = existing.metadata.resource_version
            resource["spec"]["clusterIP"] = existing.spec.cluster_ip
            v1.replace_namespaced_service(name, namespace, resource)
            logger.info("Updated Service %s", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                v1.create_namespaced_service(namespace, resource)
                logger.info("Created Service %s", name)
            else:
                raise

    elif kind == "ServiceAccount":
        v1 = kubernetes.client.CoreV1Api(api)
        try:
            v1.read_namespaced_service_account(name, namespace)
            v1.patch_namespaced_service_account(name, namespace, resource)
            logger.info("Updated ServiceAccount %s", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                v1.create_namespaced_service_account(namespace, resource)
                logger.info("Created ServiceAccount %s", name)
            else:
                raise

    elif kind == "Deployment":
        apps = kubernetes.client.AppsV1Api(api)
        try:
            apps.read_namespaced_deployment(name, namespace)
            apps.patch_namespaced_deployment(name, namespace, resource)
            logger.info("Updated Deployment %s", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                apps.create_namespaced_deployment(namespace, resource)
                logger.info("Created Deployment %s", name)
            else:
                raise

    elif kind == "StatefulSet":
        apps = kubernetes.client.AppsV1Api(api)
        try:
            apps.read_namespaced_stateful_set(name, namespace)
            apps.patch_namespaced_stateful_set(name, namespace, resource)
            logger.info("Updated StatefulSet %s", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                apps.create_namespaced_stateful_set(namespace, resource)
                logger.info("Created StatefulSet %s", name)
            else:
                raise

    elif kind == "Job":
        batch = kubernetes.client.BatchV1Api(api)
        try:
            batch.read_namespaced_job(name, namespace)
            logger.info("Job %s already exists, skipping", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                batch.create_namespaced_job(namespace, resource)
                logger.info("Created Job %s", name)
            else:
                raise

    elif kind == "ClusterRoleBinding":
        rbac = kubernetes.client.RbacAuthorizationV1Api(api)
        try:
            rbac.read_cluster_role_binding(name)
            rbac.patch_cluster_role_binding(name, resource)
            logger.info("Updated ClusterRoleBinding %s", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                rbac.create_cluster_role_binding(resource)
                logger.info("Created ClusterRoleBinding %s", name)
            else:
                raise

    elif kind == "Route":
        custom = kubernetes.client.CustomObjectsApi(api)
        try:
            custom.get_namespaced_custom_object(
                "route.openshift.io", "v1", namespace, "routes", name
            )
            custom.patch_namespaced_custom_object(
                "route.openshift.io", "v1", namespace, "routes", name, resource
            )
            logger.info("Updated Route %s", name)
        except kubernetes.client.ApiException as e:
            if e.status == 404:
                custom.create_namespaced_custom_object(
                    "route.openshift.io", "v1", namespace, "routes", resource
                )
                logger.info("Created Route %s", name)
            else:
                raise

    else:
        logger.warning("Unknown resource kind %s -- skipping", kind)


def _spec_hash(spec: dict) -> str:
    """Deterministic hash of the CR spec used as a pod annotation.

    When the spec changes, the hash changes, which updates the pod template
    annotation and triggers a rolling restart of affected Deployments.
    """
    raw = json.dumps(spec, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _inject_config_hash(resource: dict, config_hash: str) -> dict:
    """Add a config-hash annotation to pod templates in Deployments/StatefulSets."""
    kind = resource.get("kind")
    if kind in ("Deployment", "StatefulSet"):
        tpl_meta = resource["spec"]["template"].setdefault("metadata", {})
        annotations = tpl_meta.setdefault("annotations", {})
        annotations["orbit.redhat.com/config-hash"] = config_hash
    return resource


def _read_existing_secret_data(
    api: kubernetes.client.ApiClient,
    name: str,
    namespace: str,
) -> dict[str, str] | None:
    """Read current Secret data so reconciliation doesn't overwrite stable values."""
    v1 = kubernetes.client.CoreV1Api(api)
    secret_name = resource_name(name, "secrets")
    try:
        obj = v1.read_namespaced_secret(secret_name, namespace)
        if obj.data:
            return {k: base64.b64decode(v).decode() for k, v in obj.data.items()}
    except kubernetes.client.ApiException as e:
        if e.status != 404:
            raise
    return None


def reconcile_all(
    name: str,
    namespace: str,
    spec: dict,
    api: kubernetes.client.ApiClient,
) -> None:
    """Create or update every child resource for an OrbitInstance."""
    config_hash = _spec_hash(spec)
    resources: list[dict] = []

    # 1. Secrets (must come first -- others reference them)
    #    Read existing data so we never overwrite passwords/cookie-secret.
    existing_secret_data = _read_existing_secret_data(api, name, namespace)
    resources.append(
        secrets.build_app_secret(name, namespace, existing_data=existing_secret_data)
    )

    # 2. ConfigMap
    resources.append(configmap.build_configmap(name, namespace, spec))

    # 3. Auth (ServiceAccount, ClusterRoleBinding)
    resources.extend(auth.build_all(name, namespace, spec))

    # 4. PostgreSQL
    resources.append(postgres.build_service(name, namespace))
    resources.append(postgres.build_statefulset(name, namespace, spec))

    # 5. Redis
    resources.append(redis.build_service(name, namespace))
    resources.append(redis.build_deployment(name, namespace, spec))

    # 6. Backend
    resources.append(backend.build_pvc(name, namespace, spec))
    resources.append(backend.build_service(name, namespace))
    resources.append(backend.build_deployment(name, namespace, spec))

    # 7. Frontend (includes oauth-proxy sidecar)
    resources.append(frontend.build_nginx_configmap(name, namespace))
    resources.append(frontend.build_service(name, namespace))
    resources.append(frontend.build_deployment(name, namespace, spec))

    # 9. Route
    resources.append(route.build_route(name, namespace, spec))

    for res in resources:
        _inject_config_hash(res, config_hash)
        _apply(api, res, namespace)

    # 10. Migration Job (run after infra is created)
    migrate_job = migration.build_migration_job(name, namespace, spec)
    _apply(api, migrate_job, namespace)


@kopf.on.create(CRD_GROUP, CRD_VERSION, CRD_PLURAL)
def on_create(spec, name, namespace, status, patch, **_):
    """Provision a full Orbit stack when an OrbitInstance CR is created."""
    logger.info("Creating OrbitInstance %s/%s", namespace, name)

    patch.status["phase"] = "Provisioning"
    patch.status["message"] = "Creating resources..."

    api = kubernetes.client.ApiClient()
    try:
        reconcile_all(name, namespace, spec, api)
        patch.status["phase"] = "Ready"
        patch.status["message"] = "All components created"
    except Exception as exc:
        logger.exception("Failed to create OrbitInstance %s/%s", namespace, name)
        patch.status["phase"] = "Error"
        patch.status["message"] = str(exc)[:256]
        raise kopf.TemporaryError(str(exc), delay=30)
    finally:
        api.close()
