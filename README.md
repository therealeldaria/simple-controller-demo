# simple-controller-demo

A minimal demo showing how Kubernetes can act as a **control plane for external systems**.

A custom `PrimeClaim` resource is defined via a CRD. A [kopf](https://kopf.readthedocs.io/) controller watches for create/delete events and calls an external FastAPI prime-number allocator running **outside** the cluster — demonstrating the pattern without any cloud dependencies.

```
┌─────────────────────────────────────┐      HTTP       ┌───────────────────────┐
│          kind cluster               │  ────────────▶  │  FastAPI prime        │
│                                     │                 │  allocator (Docker)   │
│  kubectl apply prime-alpha.yaml     │                 │                       │
│          │                          │                 │  POST /primes         │
│          ▼                          │                 │  DELETE /primes/{n}   │
│  PrimeClaim ──▶  kopf controller    │                 │                       │
└─────────────────────────────────────┘                 └───────────────────────┘
```

---

## Prerequisites

- Docker
- `make`
- `curl`

`kind` and `kubectl` are downloaded automatically by `make prereqs`.

---

## Quick start

```bash
make prereqs   # install kind + kubectl into /usr/local/bin
make build     # build both Docker images
make setup     # create demo-net, start external API, create kind cluster
make load      # load controller image into kind
make deploy    # apply CRD, RBAC, Deployment; wait for rollout
./demo.sh      # interactive walkthrough
make teardown  # clean up everything
```

---

## Project layout

```
simple-controller-demo/
├── Makefile
├── demo.sh                            # interactive demo script
├── kind/
│   └── cluster.yaml                   # single-node kind cluster config
├── external-api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py                        # FastAPI prime allocator (runs OUTSIDE cluster)
├── controller/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── handler.py                     # kopf handlers (runs INSIDE cluster)
└── manifests/
    ├── crd.yaml
    ├── namespace.yaml
    ├── rbac.yaml
    ├── controller-deployment.yaml
    └── samples/
        ├── prime-alpha.yaml
        ├── prime-beta.yaml
        └── prime-gamma.yaml
```

---

## The PrimeClaim CRD

**Group:** `demo.example.com` | **Version:** `v1` | **Kind:** `PrimeClaim`

```yaml
apiVersion: demo.example.com/v1
kind: PrimeClaim
metadata:
  name: claim-alpha
  namespace: demo
spec:
  requester: team-alpha   # required — name of the team or service claiming a prime
```

The controller writes back to `.status`:

| Field | Description |
|---|---|
| `phase` | `Pending` / `Allocated` / `Error` |
| `prime` | The allocated prime number |
| `lastSyncTime` | ISO 8601 timestamp of last sync |
| `error` | Populated when phase is `Error` |

`kubectl get primeclaims -n demo` shows Requester, Phase, Prime, and Age columns.

---

## External API

The FastAPI service runs as a plain Docker container on port **8080**, outside the kind cluster.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Health check |
| GET | `/primes` | List all allocations |
| POST | `/primes` | Allocate the next available prime |
| DELETE | `/primes/{prime}` | Release a prime back to the pool |

---

## Drift detection

The controller runs a timer every **10 seconds**. If a prime that should be allocated is missing from the API, the controller detects the drift and re-allocates automatically — demonstrating self-healing reconciliation.

---

## Networking

The controller Pod (inside kind) reaches the external container via a shared Docker network:

1. `docker network create demo-net`
2. External API starts on `demo-net` with `--name prime-allocator-api`
3. `docker network connect demo-net demo-cluster-control-plane`
4. Docker's embedded DNS resolves `prime-allocator-api` by name inside `demo-net`

The controller Deployment sets `PRIME_API_URL=http://prime-allocator-api:8080`. Pod DNS for non-cluster names falls through to the node's `resolv.conf`, which now has access to `demo-net`.

---

## Makefile reference

| Target | Action |
|---|---|
| `make prereqs` | Download kind + kubectl to `/usr/local/bin` |
| `make build` | Build both Docker images |
| `make setup` | Create demo-net, start external API, create kind cluster, connect network |
| `make load` | Load controller image into kind via `kind load docker-image` |
| `make deploy` | Apply all manifests; wait for CRD + controller rollout |
| `make demo` | Run `./demo.sh` |
| `make logs` | Tail controller logs |
| `make status` | `kubectl get primeclaims -n demo` |
| `make teardown` | Delete cluster, stop containers, remove network |
