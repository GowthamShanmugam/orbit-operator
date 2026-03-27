"""Generate Frontend Deployment (with oauth-proxy sidecar) and Service."""

from __future__ import annotations

from orbit_operator.utils.labels import (
    resource_name,
    selector_labels,
    standard_labels,
)


def _oauth_proxy_args(name: str, spec: dict) -> list[str]:
    """Build the oauth-proxy container args based on auth provider."""
    sa_name = resource_name(name, "proxy")
    auth_spec = spec.get("auth", {})
    provider = auth_spec.get("provider", "openshift")

    args = [
        "--https-address=:8443",
        f"--upstream=http://localhost:8080",
        "--tls-cert=/etc/tls/private/tls.crt",
        "--tls-key=/etc/tls/private/tls.key",
        "--cookie-secret-file=/etc/proxy/secrets/cookie-secret",
        "--cookie-refresh=0h5m0s",
        "--pass-access-token=true",
        "--pass-user-headers=true",
        "--pass-basic-auth=false",
    ]

    if provider == "openshift":
        args += [
            "--provider=openshift",
            f"--openshift-service-account={sa_name}",
        ]
    elif provider == "rhsso":
        rhsso = auth_spec.get("rhsso", {})
        args += [
            "--provider=oidc",
            f"--oidc-issuer-url={rhsso.get('issuerUrl', '')}",
            f"--client-id={rhsso.get('clientId', '')}",
            "--client-secret-file=/etc/proxy/secrets/client-secret",
            "--email-domain=*",
        ]

    return args


def build_deployment(name: str, namespace: str, spec: dict) -> dict:
    rname = resource_name(name, "frontend")
    images = spec.get("images", {})
    frontend_image = images.get("frontend", "quay.io/gshanmug-quay/orbit-frontend:latest")
    proxy_image = images.get(
        "oauthProxy", "registry.redhat.io/openshift4/ose-oauth-proxy:latest"
    )
    replicas = spec.get("frontend", {}).get("replicas", 1)
    sa_name = resource_name(name, "proxy")
    secrets_name = resource_name(name, "secrets")
    tls_secret = f"{rname}-tls"
    backend_svc = resource_name(name, "backend")

    labels = standard_labels("frontend", name)
    match_labels = selector_labels("frontend", name)

    oauth_container = {
        "name": "oauth-proxy",
        "image": proxy_image,
        "imagePullPolicy": "Always",
        "ports": [{"containerPort": 8443, "name": "public"}],
        "args": _oauth_proxy_args(name, spec),
        "volumeMounts": [
            {"name": "proxy-tls", "mountPath": "/etc/tls/private", "readOnly": True},
            {"name": "proxy-secrets", "mountPath": "/etc/proxy/secrets", "readOnly": True},
        ],
        "resources": {
            "requests": {"cpu": "10m", "memory": "32Mi"},
            "limits": {"memory": "64Mi"},
        },
    }

    frontend_container = {
        "name": "frontend",
        "image": frontend_image,
        "imagePullPolicy": "Always",
        "ports": [{"containerPort": 8080, "name": "http"}],
        "env": [
            {"name": "BACKEND_HOST", "value": backend_svc},
            {"name": "BACKEND_PORT", "value": "8000"},
        ],
        "resources": {
            "requests": {"cpu": "50m", "memory": "64Mi"},
            "limits": {"memory": "256Mi"},
        },
    }

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": match_labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "serviceAccountName": sa_name,
                    "containers": [oauth_container, frontend_container],
                    "volumes": [
                        {
                            "name": "proxy-tls",
                            "secret": {"secretName": tls_secret},
                        },
                        {
                            "name": "proxy-secrets",
                            "secret": {"secretName": secrets_name},
                        },
                    ],
                },
            },
        },
    }


def build_service(name: str, namespace: str) -> dict:
    rname = resource_name(name, "frontend")
    tls_secret = f"{rname}-tls"
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": standard_labels("frontend", name),
            "annotations": {
                "service.beta.openshift.io/serving-cert-secret-name": tls_secret,
            },
        },
        "spec": {
            "selector": selector_labels("frontend", name),
            "ports": [
                {
                    "port": 8443,
                    "targetPort": 8443,
                    "name": "https",
                }
            ],
        },
    }
