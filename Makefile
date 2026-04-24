.PHONY: prereqs build setup load deploy demo teardown logs status

KIND_VERSION    := v0.24.0
KUBECTL_VERSION := v1.31.0
KIND_BIN        := /usr/local/bin/kind
KUBECTL_BIN     := /usr/local/bin/kubectl
CLUSTER_NAME    := demo-cluster
NETWORK_NAME    := demo-net
API_CONTAINER   := prime-api
CONTROLLER_IMAGE := localhost/prime-controller:latest
CONTAINER_ENGINE ?= docker
KIND_PROVIDER    ?=

ifeq ($(strip $(KIND_PROVIDER)),)
ifneq ($(filter podman,$(CONTAINER_ENGINE)),)
KIND_PROVIDER := podman
endif
endif

ifneq ($(strip $(KIND_PROVIDER)),)
KIND_PROVIDER_ENV := KIND_EXPERIMENTAL_PROVIDER=$(KIND_PROVIDER)
endif

# ──────────────────────────────────────────────────────────────────────────────
# prereqs: download kind and kubectl if not already installed
# ──────────────────────────────────────────────────────────────────────────────
prereqs:
	@echo "==> Checking / installing kind $(KIND_VERSION)..."
	@if ! command -v kind &>/dev/null; then \
		TMP=$$(mktemp) && \
		curl -sLo "$$TMP" \
		  "https://kind.sigs.k8s.io/dl/$(KIND_VERSION)/kind-linux-amd64" && \
		chmod +x "$$TMP" && \
		sudo mv "$$TMP" $(KIND_BIN) && echo "  kind installed"; \
	else echo "  kind already present: $$(kind version)"; fi

	@echo "==> Checking / installing kubectl $(KUBECTL_VERSION)..."
	@if ! command -v kubectl &>/dev/null; then \
		TMP=$$(mktemp) && \
		curl -sLo "$$TMP" \
		  "https://dl.k8s.io/release/$(KUBECTL_VERSION)/bin/linux/amd64/kubectl" && \
		chmod +x "$$TMP" && \
		sudo mv "$$TMP" $(KUBECTL_BIN) && echo "  kubectl installed"; \
	else echo "  kubectl already present: $$(kubectl version --client --short 2>/dev/null || kubectl version --client)"; fi

# ──────────────────────────────────────────────────────────────────────────────
# build: build both container images
# ──────────────────────────────────────────────────────────────────────────────
build:
	@echo "==> Building prime-api image with $(CONTAINER_ENGINE)..."
	$(CONTAINER_ENGINE) build -t prime-api:latest ./external-api
	@echo "==> Building prime-controller image with $(CONTAINER_ENGINE)..."
	$(CONTAINER_ENGINE) build -t prime-controller:latest -t $(CONTROLLER_IMAGE) ./controller

# ──────────────────────────────────────────────────────────────────────────────
# setup: create network, start external API, create kind cluster, connect net
# ──────────────────────────────────────────────────────────────────────────────
setup:
	@echo "==> Creating $(CONTAINER_ENGINE) network '$(NETWORK_NAME)'..."
	@$(CONTAINER_ENGINE) network inspect $(NETWORK_NAME) &>/dev/null || \
	  $(CONTAINER_ENGINE) network create $(NETWORK_NAME)

	@echo "==> Starting prime-api container..."
	@if $(CONTAINER_ENGINE) ps -a --format '{{.Names}}' | grep -q '^$(API_CONTAINER)$$'; then \
	  echo "  Container '$(API_CONTAINER)' already exists — removing..."; \
	  $(CONTAINER_ENGINE) rm -f $(API_CONTAINER); \
	fi
	$(CONTAINER_ENGINE) run -d \
	  --name $(API_CONTAINER) \
	  --network $(NETWORK_NAME) \
	  -p 8080:8080 \
	  prime-api:latest
	@echo "  Waiting for API to be ready..."
	@for i in $$(seq 1 20); do \
	  if curl -sf http://localhost:8080/ &>/dev/null; then \
	    echo "  Prime API is up."; break; \
	  fi; sleep 1; done

	@echo "==> Creating kind cluster '$(CLUSTER_NAME)'..."
	@if $(KIND_PROVIDER_ENV) kind get clusters 2>/dev/null | grep -q '^$(CLUSTER_NAME)$$'; then \
	  echo "  Cluster already exists — skipping."; \
	else \
	  $(KIND_PROVIDER_ENV) kind create cluster --config kind/cluster.yaml; \
	fi

	@echo "==> Connecting kind control-plane to demo-net..."
	@$(CONTAINER_ENGINE) network connect $(NETWORK_NAME) $(CLUSTER_NAME)-control-plane 2>/dev/null || \
	  echo "  Already connected."

	@echo "==> Setup complete."

# ──────────────────────────────────────────────────────────────────────────────
# load: load controller image into kind cluster
# ──────────────────────────────────────────────────────────────────────────────
load:
	@echo "==> Loading prime-controller image into kind..."
ifeq ($(KIND_PROVIDER),podman)
	@TMP_ARCHIVE=$$(mktemp /tmp/prime-controller-image.XXXXXX.tar); \
	  trap 'rm -f "$$TMP_ARCHIVE"' EXIT; \
	  $(CONTAINER_ENGINE) save --format docker-archive -o "$$TMP_ARCHIVE" $(CONTROLLER_IMAGE); \
	  $(KIND_PROVIDER_ENV) kind load image-archive "$$TMP_ARCHIVE" --name $(CLUSTER_NAME)
else
	$(KIND_PROVIDER_ENV) kind load docker-image $(CONTROLLER_IMAGE) --name $(CLUSTER_NAME)
endif

# ──────────────────────────────────────────────────────────────────────────────
# deploy: apply manifests and wait for rollout
# ──────────────────────────────────────────────────────────────────────────────
deploy:
	@echo "==> Applying manifests..."
	kubectl apply -f manifests/namespace.yaml
	kubectl apply -f manifests/crd.yaml
	@echo "  Waiting for CRD to be established..."
	kubectl wait --for=condition=Established crd/primeclaims.demo.example.com --timeout=60s
	kubectl apply -f manifests/rbac.yaml
	kubectl apply -f manifests/controller-deployment.yaml
	@echo "  Waiting for controller rollout..."
	kubectl rollout status deployment/prime-controller -n demo --timeout=120s
	@echo "==> Deploy complete."

# ──────────────────────────────────────────────────────────────────────────────
# demo: interactive walkthrough
# ──────────────────────────────────────────────────────────────────────────────
demo:
	@./demo.sh

# ──────────────────────────────────────────────────────────────────────────────
# logs: tail controller logs
# ──────────────────────────────────────────────────────────────────────────────
logs:
	kubectl logs -n demo -l app=prime-controller -f

# ──────────────────────────────────────────────────────────────────────────────
# status: show all prime claims
# ──────────────────────────────────────────────────────────────────────────────
status:
	kubectl get primeclaims -n demo

# ──────────────────────────────────────────────────────────────────────────────
# teardown: clean up everything
# ──────────────────────────────────────────────────────────────────────────────
teardown:
	@echo "==> Deleting kind cluster..."
	$(KIND_PROVIDER_ENV) kind delete cluster --name $(CLUSTER_NAME) || true
	@echo "==> Stopping prime-api container..."
	$(CONTAINER_ENGINE) rm -f $(API_CONTAINER) || true
	@echo "==> Removing network..."
	$(CONTAINER_ENGINE) network rm $(NETWORK_NAME) || true
	@echo "==> Teardown complete."
