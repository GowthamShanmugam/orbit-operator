"""Periodic health-check timer that updates OrbitInstance .status fields."""

from __future__ import annotations

import logging

import kopf
import kubernetes

from orbit_operator.handlers.create import CRD_GROUP, CRD_PLURAL, CRD_VERSION
from orbit_operator.utils.labels import resource_name

logger = logging.getLogger(__name__)

_INTERVAL = 30  # seconds between health checks


def _deployment_status(apps: kubernetes.client.AppsV1Api, name: str, ns: str) -> str:
    """Return a human-readable status string for a Deployment."""
    try:
        d = apps.read_namespaced_deployment(name, ns)
        ready = d.status.ready_replicas or 0
        desired = d.spec.replicas or 0
        if ready >= desired:
            return f"Running ({ready}/{desired})"
        return f"Pending ({ready}/{desired})"
    except kubernetes.client.ApiException as e:
        if e.status == 404:
            return "NotFound"
        return f"Error ({e.status})"


def _statefulset_status(apps: kubernetes.client.AppsV1Api, name: str, ns: str) -> str:
    """Return a human-readable status string for a StatefulSet."""
    try:
        ss = apps.read_namespaced_stateful_set(name, ns)
        ready = ss.status.ready_replicas or 0
        desired = ss.spec.replicas or 0
        if ready >= desired:
            return f"Running ({ready}/{desired})"
        return f"Pending ({ready}/{desired})"
    except kubernetes.client.ApiException as e:
        if e.status == 404:
            return "NotFound"
        return f"Error ({e.status})"


def _route_url(
    custom: kubernetes.client.CustomObjectsApi, name: str, ns: str
) -> str | None:
    """Read the Route's .spec.host to derive the external URL."""
    try:
        rt = custom.get_namespaced_custom_object(
            "route.openshift.io", "v1", ns, "routes", name
        )
        host = rt.get("spec", {}).get("host")
        if host:
            return f"https://{host}"
    except kubernetes.client.ApiException:
        pass
    return None


@kopf.timer(CRD_GROUP, CRD_VERSION, CRD_PLURAL, interval=_INTERVAL, sharp=True)
def health_check(spec, name, namespace, patch, **_):
    """Periodically update the CR status with component health."""
    api = kubernetes.client.ApiClient()
    try:
        apps = kubernetes.client.AppsV1Api(api)
        custom = kubernetes.client.CustomObjectsApi(api)

        components = {
            "postgres": _statefulset_status(apps, resource_name(name, "db"), namespace),
            "redis": _deployment_status(apps, resource_name(name, "redis"), namespace),
            "backend": _deployment_status(apps, resource_name(name, "backend"), namespace),
            "frontend": _deployment_status(
                apps, resource_name(name, "frontend"), namespace
            ),
        }

        all_running = all("Running" in v for v in components.values())
        any_error = any("Error" in v or "NotFound" in v for v in components.values())

        if any_error:
            phase = "Error"
            message = "One or more components unhealthy"
        elif all_running:
            phase = "Ready"
            message = "All components healthy"
        else:
            phase = "Provisioning"
            message = "Some components still starting"

        route_url = _route_url(custom, name, namespace)

        patch.status["phase"] = phase
        patch.status["message"] = message
        patch.status["components"] = components
        if route_url:
            patch.status["route"] = route_url

    except Exception:
        logger.exception("Error during health check for %s/%s", namespace, name)
    finally:
        api.close()
