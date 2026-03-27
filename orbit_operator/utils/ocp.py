"""OpenShift-specific helpers."""

from __future__ import annotations

import logging

import kubernetes

logger = logging.getLogger(__name__)

ROUTE_API_GROUP = "route.openshift.io"
ROUTE_API_VERSION = "v1"


def is_openshift(api_client: kubernetes.client.ApiClient | None = None) -> bool:
    """Return True if the cluster exposes the OpenShift Route API."""
    try:
        api = kubernetes.client.ApisApi(api_client)
        groups = api.get_api_versions()
        for g in groups.groups:
            if g.name == ROUTE_API_GROUP:
                return True
    except Exception:
        logger.debug("Could not detect OpenShift API groups", exc_info=True)
    return False


def oauth_proxy_image() -> str:
    """Return the recommended oauth-proxy image for the cluster."""
    return "registry.redhat.io/openshift4/ose-oauth-proxy:latest"
