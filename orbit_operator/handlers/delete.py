"""Handler for OrbitInstance deletion -- cleans up cluster-scoped resources."""

from __future__ import annotations

import logging

import kopf
import kubernetes

from orbit_operator.handlers.create import CRD_GROUP, CRD_PLURAL, CRD_VERSION
from orbit_operator.utils.labels import resource_name

logger = logging.getLogger(__name__)


@kopf.on.delete(CRD_GROUP, CRD_VERSION, CRD_PLURAL)
def on_delete(name, namespace, **_):
    """Clean up cluster-scoped resources that Kubernetes GC won't handle.

    Namespaced resources with ownerReferences are garbage-collected
    automatically. We only need to delete ClusterRoleBindings and Routes
    (OCP custom objects that may not have owner refs).
    """
    logger.info("Deleting OrbitInstance %s/%s -- cleaning up", namespace, name)

    api = kubernetes.client.ApiClient()
    try:
        _delete_cluster_role_binding(api, name, namespace)
        _delete_route(api, name, namespace)
    except Exception:
        logger.exception("Error during cleanup of %s/%s", namespace, name)
    finally:
        api.close()


def _delete_cluster_role_binding(
    api: kubernetes.client.ApiClient, name: str, namespace: str
) -> None:
    crb_name = resource_name(name, "auth-delegator")
    rbac = kubernetes.client.RbacAuthorizationV1Api(api)
    try:
        rbac.delete_cluster_role_binding(crb_name)
        logger.info("Deleted ClusterRoleBinding %s", crb_name)
    except kubernetes.client.ApiException as e:
        if e.status != 404:
            raise


def _delete_route(api: kubernetes.client.ApiClient, name: str, namespace: str) -> None:
    custom = kubernetes.client.CustomObjectsApi(api)
    try:
        custom.delete_namespaced_custom_object(
            "route.openshift.io", "v1", namespace, "routes", name
        )
        logger.info("Deleted Route %s/%s", namespace, name)
    except kubernetes.client.ApiException as e:
        if e.status != 404:
            raise
