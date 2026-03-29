.PHONY: prereqs build setup load deploy demo teardown logs status

KIND_VERSION   := v0.24.0
KUBECTL_VERSION := v1.31.0
KIND_BIN       := /usr/local/bin/kind
KUBECTL_BIN    := /usr/local/bin/kubectl
CLUSTER_NAME   := demo-cluster
NETWORK_NAME   := demo-net
API_CONTAINER  := message-board-api

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
# build: build both Docker images
# ──────────────────────────────────────────────────────────────────────────────
build:
	@echo "==> Building external-api image..."
	docker build -t message-board-api:latest ./external-api
	@echo "==> Building controller image..."
	docker build -t message-controller:latest ./controller

# ──────────────────────────────────────────────────────────────────────────────
# setup: create network, start external API, create kind cluster, connect net
# ──────────────────────────────────────────────────────────────────────────────
setup:
	@echo "==> Creating Docker network '$(NETWORK_NAME)'..."
	@docker network inspect $(NETWORK_NAME) &>/dev/null || \
	  docker network create $(NETWORK_NAME)

	@echo "==> Starting external API container..."
	@if docker ps -a --format '{{.Names}}' | grep -q '^$(API_CONTAINER)$$'; then \
	  echo "  Container '$(API_CONTAINER)' already exists — removing..."; \
	  docker rm -f $(API_CONTAINER); \
	fi
	docker run -d \
	  --name $(API_CONTAINER) \
	  --network $(NETWORK_NAME) \
	  -p 8080:8080 \
	  message-board-api:latest
	@echo "  Waiting for API to be ready..."
	@for i in $$(seq 1 20); do \
	  if curl -sf http://localhost:8080/ &>/dev/null; then \
	    echo "  External API is up."; break; \
	  fi; sleep 1; done

	@echo "==> Creating kind cluster '$(CLUSTER_NAME)'..."
	@if kind get clusters 2>/dev/null | grep -q '^$(CLUSTER_NAME)$$'; then \
	  echo "  Cluster already exists — skipping."; \
	else \
	  kind create cluster --config kind/cluster.yaml; \
	fi

	@echo "==> Connecting kind control-plane to demo-net..."
	@docker network connect $(NETWORK_NAME) $(CLUSTER_NAME)-control-plane 2>/dev/null || \
	  echo "  Already connected."

	@echo "==> Setup complete."

# ──────────────────────────────────────────────────────────────────────────────
# load: load controller image into kind cluster
# ──────────────────────────────────────────────────────────────────────────────
load:
	@echo "==> Loading controller image into kind..."
	kind load docker-image message-controller:latest --name $(CLUSTER_NAME)

# ──────────────────────────────────────────────────────────────────────────────
# deploy: apply manifests and wait for rollout
# ──────────────────────────────────────────────────────────────────────────────
deploy:
	@echo "==> Applying manifests..."
	kubectl apply -f manifests/namespace.yaml
	kubectl apply -f manifests/crd.yaml
	@echo "  Waiting for CRD to be established..."
	kubectl wait --for=condition=Established crd/messages.demo.example.com --timeout=60s
	kubectl apply -f manifests/rbac.yaml
	kubectl apply -f manifests/controller-deployment.yaml
	@echo "  Waiting for controller rollout..."
	kubectl rollout status deployment/message-controller -n demo --timeout=120s
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
	kubectl logs -n demo -l app=message-controller -f

# ──────────────────────────────────────────────────────────────────────────────
# status: show all messages
# ──────────────────────────────────────────────────────────────────────────────
status:
	kubectl get messages -n demo

# ──────────────────────────────────────────────────────────────────────────────
# teardown: clean up everything
# ──────────────────────────────────────────────────────────────────────────────
teardown:
	@echo "==> Deleting kind cluster..."
	kind delete cluster --name $(CLUSTER_NAME) || true
	@echo "==> Stopping API container..."
	docker rm -f $(API_CONTAINER) || true
	@echo "==> Removing network..."
	docker network rm $(NETWORK_NAME) || true
	@echo "==> Teardown complete."
