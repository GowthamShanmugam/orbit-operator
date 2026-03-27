# Orbit Operator for OpenShift

An OpenShift operator that deploys and manages **Orbit** -- an AI-powered IDE platform -- as a fully managed stack on OpenShift Container Platform (OCP).

## What It Does

When you create an `OrbitInstance` custom resource, the operator provisions:

| Component | Kind | Description |
|-----------|------|-------------|
| PostgreSQL (pgvector) | StatefulSet | Database with vector search support |
| Redis | Deployment | Cache and Celery message broker |
| Backend API | Deployment | FastAPI application server |
| Celery Worker | Deployment | Background task processor |
| Frontend | Deployment | React/Vite UI + oauth-proxy sidecar |
| Route | Route | TLS-terminated external access |
| Auth | ServiceAccount + CRB | OpenShift OAuth / Red Hat SSO integration |

The operator continuously monitors component health and reports status on the CR.

## Prerequisites

- OpenShift 4.12+
- `oc` CLI logged in as cluster-admin (for CRD + RBAC installation)
- Container images published to a registry accessible from the cluster (defaults: `quay.io/gshanmug-quay/orbit-backend`, `quay.io/gshanmug-quay/orbit-frontend`)

## Quick Start

```bash
# 1. Create the operator namespace
oc new-project orbit-operator

# 2. Install CRD, RBAC, and operator
oc apply -f config/crd/
oc apply -f config/rbac/
oc apply -f config/manager/

# 3. Create the application namespace
oc new-project orbit

# 4. (If using Vertex AI) Create the GCP SA secret
oc create secret generic orbit-gcp-sa \
  --from-file=sa-key.json=/path/to/service-account-key.json \
  -n orbit

# 5. Edit the sample CR with your settings, then apply
oc apply -f config/samples/orbit_v1alpha1_orbitinstance.yaml

# 6. Watch provisioning progress
oc get orbitinstance orbit -n orbit -w
```

## Authentication

### OpenShift OAuth (default)

Set `spec.auth.provider: openshift`. The operator creates a ServiceAccount with an OAuth redirect annotation, and the oauth-proxy sidecar handles login via OpenShift's built-in OAuth server. No additional configuration needed.

### Red Hat SSO / Keycloak

```yaml
spec:
  auth:
    provider: rhsso
    rhsso:
      issuerUrl: https://sso.example.com/realms/orbit
      clientId: orbit
      clientSecret:
        secretRef: orbit-sso-secret
        key: client-secret
```

Create the client secret beforehand:
```bash
oc create secret generic orbit-sso-secret \
  --from-literal=client-secret=YOUR_CLIENT_SECRET \
  -n orbit
```

## AI Provider Configuration

### Vertex AI (default)

```yaml
spec:
  ai:
    provider: vertex
    vertexProjectId: my-gcp-project
    vertexRegion: us-east5
  gcp:
    serviceAccountSecret: orbit-gcp-sa
```

### Direct Anthropic API Key

```yaml
spec:
  ai:
    provider: anthropic
    anthropicApiKeySecret:
      secretRef: orbit-anthropic-key
      key: api-key
```

## Development

### Run Operator Locally

```bash
# Install dependencies
pip install -e ".[dev]"

# Install CRD
make install-crd

# Run the operator (watches all namespaces)
make run
```

### Build and Push

```bash
# Build operator image
make build

# Push to registry
make push

# Deploy to cluster
make deploy
```

## Status Monitoring

The operator updates the CR status every 30 seconds:

```bash
oc get orbitinstance orbit -n orbit -o yaml
```

```yaml
status:
  phase: Ready
  message: All components healthy
  route: https://orbit.apps.cluster.example.com
  components:
    postgres: "Running (1/1)"
    redis: "Running (1/1)"
    backend: "Running (2/2)"
    celery: "Running (1/1)"
    frontend: "Running (1/1)"
```

## Project Structure

```
orbit-operator/
  orbit_operator/           # Python operator code
    handlers/               # Kopf event handlers (create, update, delete, status)
    resources/              # Kubernetes resource generators
    utils/                  # Labels, OCP helpers
  config/
    crd/                    # CustomResourceDefinition
    rbac/                   # Operator RBAC (ClusterRole, Binding, SA)
    manager/                # Operator Deployment manifest
    samples/                # Example OrbitInstance CR
  bundle/                   # OLM bundle (for OperatorHub publishing)
  Containerfile             # Operator container image
  Makefile                  # Build/deploy shortcuts
```

## License

Apache License 2.0
