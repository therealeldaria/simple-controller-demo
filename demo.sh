#!/usr/bin/env bash
# Interactive demo walkthrough for the PrimeClaim CRD/CR/Controller demo.
set -euo pipefail

CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
BOLD="\033[1m"
RESET="\033[0m"

step() { echo -e "\n${CYAN}${BOLD}==> $*${RESET}"; }
info() { echo -e "${YELLOW}    $*${RESET}"; }
ok()   { echo -e "${GREEN}    $*${RESET}"; }

pause() {
  echo -e "\n${BOLD}[Press ENTER to continue...]${RESET}"
  read -r
}

# ── 1. Show the cluster is healthy ──────────────────────────────────────────
step "Step 1 — Cluster is healthy"
kubectl cluster-info --context kind-demo-cluster
pause

# ── 2. External API + open dashboard ────────────────────────────────────────
step "Step 2 — Prime API health check + dashboard"
info "The FastAPI prime reservation service runs OUTSIDE the kind cluster as a plain container."
curl -s http://localhost:8080/ | python3 -m json.tool
echo ""
ok "Dashboard available at: http://localhost:8080/ui"
info "Opening in browser..."
xdg-open http://localhost:8080/ui 2>/dev/null || open http://localhost:8080/ui 2>/dev/null || true
pause

# ── 3. Show the CRD ─────────────────────────────────────────────────────────
step "Step 3 — Inspect the CRD"
kubectl get crd primeclaims.demo.example.com
echo ""
kubectl explain primeclaim.spec
pause

# ── 4. No allocations yet ───────────────────────────────────────────────────
step "Step 4 — No primes allocated yet"
info "Prime API allocations:"
curl -s http://localhost:8080/primes | python3 -m json.tool
pause

# ── 5. Claim alpha — gets prime 2 ───────────────────────────────────────────
step "Step 5 — Create first PrimeClaim (team-alpha)"
info "Applying manifests/samples/prime-alpha.yaml..."
kubectl apply -f manifests/samples/prime-alpha.yaml
echo ""
info "Waiting for controller to allocate a prime..."
for i in $(seq 1 30); do
  PHASE=$(kubectl get primeclaim claim-alpha -n demo -o jsonpath='{.status.phase}' 2>/dev/null || true)
  if [[ "$PHASE" == "Allocated" ]]; then
    ok "Phase = Allocated"
    break
  fi
  sleep 1
done
echo ""
kubectl get primeclaims -n demo
pause

# ── 6. Check external API ───────────────────────────────────────────────────
step "Step 6 — Prime is registered in the external API"
curl -s http://localhost:8080/primes | python3 -m json.tool
pause

# ── 7. Claim beta — gets next prime ─────────────────────────────────────────
step "Step 7 — Create second PrimeClaim (team-beta)"
kubectl apply -f manifests/samples/prime-beta.yaml
for i in $(seq 1 30); do
  PHASE=$(kubectl get primeclaim claim-beta -n demo -o jsonpath='{.status.phase}' 2>/dev/null || true)
  if [[ "$PHASE" == "Allocated" ]]; then
    ok "Phase = Allocated"
    break
  fi
  sleep 1
done
echo ""
kubectl get primeclaims -n demo
echo ""
info "External API now shows two allocations:"
curl -s http://localhost:8080/primes | python3 -m json.tool
pause

# ── 8. Claim gamma — gets next prime ────────────────────────────────────────
step "Step 8 — Create third PrimeClaim (team-gamma)"
kubectl apply -f manifests/samples/prime-gamma.yaml
for i in $(seq 1 30); do
  PHASE=$(kubectl get primeclaim claim-gamma -n demo -o jsonpath='{.status.phase}' 2>/dev/null || true)
  if [[ "$PHASE" == "Allocated" ]]; then
    ok "Phase = Allocated"
    break
  fi
  sleep 1
done
echo ""
kubectl get primeclaims -n demo
echo ""
info "External API — three primes allocated (2, 3, 5):"
curl -s http://localhost:8080/primes | python3 -m json.tool
pause

# ── 9. Release claim-beta ────────────────────────────────────────────────────
step "Step 9 — Delete a PrimeClaim (controller releases prime back to pool)"
kubectl delete primeclaim claim-beta -n demo
info "Waiting for deletion to propagate..."
sleep 3
echo ""
info "External API — prime 3 is now free again:"
curl -s http://localhost:8080/primes | python3 -m json.tool
pause

# ── 10. Show controller logs ─────────────────────────────────────────────────
step "Step 10 — Recent controller logs"
kubectl logs -n demo -l app=prime-controller --tail=40
pause

# ── Final summary ────────────────────────────────────────────────────────────
step "Demo complete!"
echo ""
ok "What we demonstrated:"
echo "  1. A CRD (CustomResourceDefinition) extends the Kubernetes API with a 'PrimeClaim' type."
echo "  2. A kopf controller watches PrimeClaim CRs inside the kind cluster."
echo "  3. On create, the controller calls the external API to allocate the next available prime."
echo "  4. On delete, the controller releases the prime back to the pool."
echo "  5. Kubernetes acted as a control plane for an external reservation system."
echo ""
info "To clean up: make teardown"
