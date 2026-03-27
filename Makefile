IMAGE_REGISTRY ?= quay.io
IMAGE_ORG ?= gshanmug-quay
OPERATOR_IMG ?= $(IMAGE_REGISTRY)/$(IMAGE_ORG)/orbit-operator:$(VERSION)
BUNDLE_IMG ?= $(IMAGE_REGISTRY)/$(IMAGE_ORG)/orbit-operator-bundle:$(VERSION)
VERSION ?= 0.1.0

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install-crd
install-crd: ## Install the CRD into the current cluster
	oc apply -f config/crd/

.PHONY: uninstall-crd
uninstall-crd: ## Remove the CRD from the current cluster
	oc delete -f config/crd/

.PHONY: run
run: ## Run the operator locally (outside the cluster)
	kopf run --standalone orbit_operator/main.py --verbose

.PHONY: deploy
deploy: ## Deploy operator + RBAC + CRD into the cluster
	oc apply -f config/crd/
	oc apply -f config/rbac/
	oc apply -f config/manager/

.PHONY: undeploy
undeploy: ## Remove operator + RBAC + CRD from the cluster
	oc delete -f config/manager/ --ignore-not-found
	oc delete -f config/rbac/ --ignore-not-found
	oc delete -f config/crd/ --ignore-not-found

.PHONY: build
build: ## Build the operator container image
	podman build -t $(OPERATOR_IMG) -f Containerfile .

.PHONY: push
push: ## Push the operator container image
	podman push $(OPERATOR_IMG)

.PHONY: bundle-build
bundle-build: ## Build the OLM bundle image
	podman build -t $(BUNDLE_IMG) -f bundle/bundle.Dockerfile bundle/

.PHONY: bundle-push
bundle-push: ## Push the OLM bundle image
	podman push $(BUNDLE_IMG)

.PHONY: lint
lint: ## Lint Python code
	ruff check orbit_operator/

.PHONY: test
test: ## Run unit tests
	pytest tests/ -v

.PHONY: sample
sample: ## Apply the sample OrbitInstance CR
	oc apply -f config/samples/orbit_v1alpha1_orbitinstance.yaml
