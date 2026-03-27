"""Generate the OpenShift Route for an OrbitInstance."""

from __future__ import annotations

from orbit_operator.utils.labels import resource_name, standard_labels


def build_route(name: str, namespace: str, spec: dict) -> dict:
    """Build a TLS re-encrypt Route pointing to the frontend service.

    OCP auto-provisions the default *.apps wildcard certificate on the
    edge, and the service-serving CA provides the backend cert via the
    serving-cert annotation on the Service.
    """
    frontend_svc = resource_name(name, "frontend")

    return {
        "apiVersion": "route.openshift.io/v1",
        "kind": "Route",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": standard_labels("route", name),
        },
        "spec": {
            "to": {
                "kind": "Service",
                "name": frontend_svc,
                "weight": 100,
            },
            "port": {
                "targetPort": "https",
            },
            "tls": {
                "termination": "reencrypt",
                "insecureEdgeTerminationPolicy": "Redirect",
            },
        },
    }
