# simple-controller-demo

A minimal demo showing how Kubernetes can act as a **control plane for external systems**.

A custom `Message` resource is defined via a CRD. A [kopf](https://kopf.readthedocs.io/) controller watches for create/update/delete events and calls an external FastAPI message board running **outside** the cluster — demonstrating the pattern without any cloud dependencies.

```
┌─────────────────────────────────────┐      HTTP      ┌──────────────────────┐
│          kind cluster               │  ────────────▶  │  FastAPI message      │
│                                     │                 │  board (Docker)       │
│  kubectl apply message-hello.yaml   │                 │                       │
│          │                          │                 │  POST /boards/general │
│          ▼                          │                 │  PUT  /boards/…/…     │
│   Message CR  ──▶  kopf controller  │                 │  DELETE /boards/…/…   │
└─────────────────────────────────────┘                 └──────────────────────┘
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
│   └── main.py                        # FastAPI message board (runs OUTSIDE cluster)
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
        ├── message-hello.yaml
        ├── message-update.yaml
        └── message-goodbye.yaml
```

---

## The Message CRD

**Group:** `demo.example.com` | **Version:** `v1` | **Kind:** `Message`

```yaml
apiVersion: demo.example.com/v1
kind: Message
metadata:
  name: hello-world
  namespace: demo
spec:
  author: Alice          # required
  title: Hello, World!  # required
  body: My first post.  # required
  board: general         # optional, default: general
```

The controller writes back to `.status`:

| Field | Description |
|---|---|
| `phase` | `Pending` / `Posted` / `Updated` / `Deleted` / `Error` |
| `messageId` | UUID assigned by the external API |
| `boardUrl` | Path returned by the external API |
| `lastSyncTime` | ISO 8601 timestamp of last sync |
| `error` | Populated when phase is `Error` |

`kubectl get messages -n demo` shows Author, Board, Phase, MessageID, and Age columns.

---

## External API

The FastAPI service runs as a plain Docker container on port **8080**, outside the kind cluster.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Health check |
| GET | `/boards` | List all boards |
| GET | `/boards/{board}` | List messages on a board |
| POST | `/boards/{board}/messages` | Create a message |
| PUT | `/boards/{board}/messages/{id}` | Update a message |
| DELETE | `/boards/{board}/messages/{id}` | Delete a message |

---

## Networking

The controller Pod (inside kind) reaches the external container via a shared Docker network:

1. `docker network create demo-net`
2. External API starts on `demo-net` with `--name message-board-api`
3. `docker network connect demo-net demo-cluster-control-plane`
4. Docker's embedded DNS resolves `message-board-api` by name inside `demo-net`

The controller Deployment sets `MESSAGE_BOARD_URL=http://message-board-api:8080`. Pod DNS for non-cluster names falls through to the node's `resolv.conf`, which now has access to `demo-net`.

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
| `make status` | `kubectl get messages -n demo` |
| `make teardown` | Delete cluster, stop containers, remove network |
