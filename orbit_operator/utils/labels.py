"""Standard Kubernetes labels and selectors for Orbit resources."""

from __future__ import annotations

APP_NAME = "orbit"
OPERATOR_NAME = "orbit-operator"


def standard_labels(component: str, instance_name: str) -> dict[str, str]:
    """Return the standard set of labels for a managed resource."""
    return {
        "app.kubernetes.io/name": APP_NAME,
        "app.kubernetes.io/instance": instance_name,
        "app.kubernetes.io/component": component,
        "app.kubernetes.io/managed-by": OPERATOR_NAME,
    }


def selector_labels(component: str, instance_name: str) -> dict[str, str]:
    """Immutable subset of labels used in matchLabels / selectors."""
    return {
        "app.kubernetes.io/name": APP_NAME,
        "app.kubernetes.io/instance": instance_name,
        "app.kubernetes.io/component": component,
    }


def resource_name(instance_name: str, component: str) -> str:
    """Derive a child resource name from the CR instance name and component."""
    return f"{instance_name}-{component}"
