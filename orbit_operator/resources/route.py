"""Generate the OpenShift Route for an OrbitInstance."""

from __future__ import annotations

from orbit_operator.utils.labels import resource_name, standard_labels


def build_route(name: str, namespace: str, spec: dict) -> dict:
    """Build a TLS Route for the OrbitInstance.

    OpenShift provider: re-encrypt Route → frontend Service (ose-oauth-proxy on 8443).
    RHSSO provider: edge Route → oauth2-proxy Service (plain HTTP on 4180).
    """
    provider = spec.get("auth", {}).get("provider", "openshift")

    if provider == "rhsso":
        target_svc = resource_name(name, "oauth2-proxy")
        target_port = "http"
        tls = {
            "termination": "edge",
            "insecureEdgeTerminationPolicy": "Redirect",
        }
    else:
        target_svc = resource_name(name, "frontend")
        target_port = "https"
        tls = {
            "termination": "reencrypt",
            "insecureEdgeTerminationPolicy": "Redirect",
        }

    return {
        "apiVersion": "route.openshift.io/v1",
        "kind": "Route",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": standard_labels("route", name),
            "annotations": {
                "haproxy.router.openshift.io/timeout": "3000s",
            },
        },
        "spec": {
            "to": {
                "kind": "Service",
                "name": target_svc,
                "weight": 100,
            },
            "port": {
                "targetPort": target_port,
            },
            "tls": tls,
        },
    }
