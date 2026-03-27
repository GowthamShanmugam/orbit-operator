"""Handler for OrbitInstance spec changes -- reconciles child resources."""

from __future__ import annotations

import logging

import kopf
import kubernetes

from orbit_operator.handlers.create import CRD_GROUP, CRD_PLURAL, CRD_VERSION, reconcile_all

logger = logging.getLogger(__name__)


@kopf.on.update(CRD_GROUP, CRD_VERSION, CRD_PLURAL, field="spec")
def on_spec_change(spec, name, namespace, patch, **_):
    """Re-reconcile all resources when the CR spec changes."""
    logger.info("Spec changed for OrbitInstance %s/%s -- reconciling", namespace, name)

    patch.status["phase"] = "Provisioning"
    patch.status["message"] = "Applying spec changes..."

    api = kubernetes.client.ApiClient()
    try:
        reconcile_all(name, namespace, spec, api)
        patch.status["phase"] = "Ready"
        patch.status["message"] = "Spec changes applied"
    except Exception as exc:
        logger.exception("Failed to reconcile OrbitInstance %s/%s", namespace, name)
        patch.status["phase"] = "Error"
        patch.status["message"] = str(exc)[:256]
        raise kopf.TemporaryError(str(exc), delay=30)
    finally:
        api.close()
