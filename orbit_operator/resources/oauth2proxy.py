"""Generate standalone oauth2-proxy Deployment and Service for RHSSO/OIDC auth."""

from __future__ import annotations

from orbit_operator.utils.labels import resource_name, selector_labels, standard_labels

_DEFAULT_IMAGE = "quay.io/oauth2-proxy/oauth2-proxy:v7.6.0"


def build_deployment(name: str, namespace: str, spec: dict) -> dict:
    rname = resource_name(name, "oauth2-proxy")
    images = spec.get("images", {})
    image = images.get("oauth2Proxy", _DEFAULT_IMAGE)

    auth = spec.get("auth", {})
    rhsso = auth.get("rhsso", {})
    client_secret_ref = rhsso.get("clientSecret", {})
    secrets_name = resource_name(name, "secrets")
    frontend_svc = resource_name(name, "frontend")

    labels = standard_labels("oauth2-proxy", name)
    match_labels = selector_labels("oauth2-proxy", name)

    env = [
        {"name": "OAUTH2_PROXY_HTTP_ADDRESS", "value": "0.0.0.0:4180"},
        {"name": "OAUTH2_PROXY_PROVIDER", "value": "oidc"},
        {"name": "OAUTH2_PROXY_OIDC_ISSUER_URL", "value": rhsso.get("issuerUrl", "")},
        {"name": "OAUTH2_PROXY_CLIENT_ID", "value": rhsso.get("clientId", "")},
        {
            "name": "OAUTH2_PROXY_CLIENT_SECRET",
            "valueFrom": {
                "secretKeyRef": {
                    "name": client_secret_ref.get("secretRef", ""),
                    "key": client_secret_ref.get("key", "client-secret"),
                }
            },
        },
        {
            "name": "OAUTH2_PROXY_COOKIE_SECRET",
            "valueFrom": {
                "secretKeyRef": {
                    "name": secrets_name,
                    "key": "cookie-secret",
                }
            },
        },
        {"name": "OAUTH2_PROXY_UPSTREAMS", "value": f"http://{frontend_svc}:8080/"},
        {"name": "OAUTH2_PROXY_EMAIL_DOMAINS", "value": "*"},
        {"name": "OAUTH2_PROXY_COOKIE_SECURE", "value": "true"},
        {"name": "OAUTH2_PROXY_PROXY_PREFIX", "value": "/oauth2"},
        {"name": "OAUTH2_PROXY_SET_XAUTHREQUEST", "value": "true"},
        {"name": "OAUTH2_PROXY_PASS_ACCESS_TOKEN", "value": "true"},
    ]

    redirect_url = rhsso.get("redirectUrl", "")
    if redirect_url:
        env.append({"name": "OAUTH2_PROXY_REDIRECT_URL", "value": redirect_url})

    container = {
        "name": "oauth2-proxy",
        "image": image,
        "ports": [{"containerPort": 4180, "name": "http"}],
        "env": env,
        "resources": {
            "requests": {"cpu": "50m", "memory": "64Mi"},
            "limits": {"memory": "256Mi"},
        },
        "readinessProbe": {
            "httpGet": {"path": "/ping", "port": 4180},
            "initialDelaySeconds": 5,
            "periodSeconds": 10,
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
            "replicas": 1,
            "selector": {"matchLabels": match_labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [container],
                },
            },
        },
    }


def build_service(name: str, namespace: str) -> dict:
    rname = resource_name(name, "oauth2-proxy")
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": rname,
            "namespace": namespace,
            "labels": standard_labels("oauth2-proxy", name),
        },
        "spec": {
            "selector": selector_labels("oauth2-proxy", name),
            "ports": [{"port": 4180, "targetPort": 4180, "name": "http"}],
        },
    }
