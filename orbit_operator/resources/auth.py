"""Generate ServiceAccount, ClusterRoleBinding, and cookie secret for oauth-proxy."""

from __future__ import annotations

import json

from orbit_operator.utils.labels import resource_name, standard_labels


def _sa_name(instance_name: str) -> str:
    return resource_name(instance_name, "proxy")


def build_service_account(name: str, namespace: str, spec: dict) -> dict:
    """Build the ServiceAccount used by oauth-proxy.

    The annotation tells OCP's OAuth server to accept redirects to the Route.
    """
    sa = _sa_name(name)
    redirect_ref = json.dumps(
        {
            "kind": "OAuthRedirectReference",
            "apiVersion": "v1",
            "reference": {"kind": "Route", "name": name},
        }
    )

    return {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": sa,
            "namespace": namespace,
            "labels": standard_labels("auth", name),
            "annotations": {
                "serviceaccounts.openshift.io/oauth-redirectreference.primary": redirect_ref,
            },
        },
    }


def build_cluster_role_binding(name: str, namespace: str) -> dict:
    """Grant the proxy SA the system:auth-delegator role (required since OCP 4.9)."""
    crb_name = resource_name(name, "auth-delegator")
    sa = _sa_name(name)
    return {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRoleBinding",
        "metadata": {
            "name": crb_name,
            "labels": standard_labels("auth", name),
        },
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "ClusterRole",
            "name": "system:auth-delegator",
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": sa,
                "namespace": namespace,
            }
        ],
    }


def build_all(name: str, namespace: str, spec: dict) -> list[dict]:
    """Return all auth-related resources."""
    return [
        build_service_account(name, namespace, spec),
        build_cluster_role_binding(name, namespace),
    ]
