---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Segoe UI', sans-serif;
  }
  section.lead h1 {
    font-size: 2.2em;
  }
  pre {
    font-size: 0.75em;
  }
  code {
    font-size: 0.85em;
  }
  .columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5em;
  }
---

<!-- _class: lead -->

# Kubernetes som kontrollplan
### för externa system

En demo med **Custom Resources** och **kopf**

---

## Problemet vi löser

> "Hur kan Kubernetes hantera resurser som **inte** lever inuti klustret?"

Exempel:
- Primtalsreservationer i en extern tjänst
- En databas utanför klustret
- Ett externt SaaS-system

**Lösning:** Definiera egna resurser i Kubernetes och låt en *controller* synkronisera mot det externa systemet.

---

## Demots arkitektur

```
┌─────────────────────────────────────┐      HTTP       ┌──────────────────────┐
│          kind cluster               │ ──────────────▶ │  FastAPI prime-api   │
│                                     │                  │  (Docker container)  │
│  kubectl apply claim-alpha.yaml     │                  │                      │
│          │                          │                  │  POST /primes        │
│          ▼                          │                  │  DELETE /primes/{n}  │
│  PrimeClaim CR ──▶ kopf controller  │                  │  GET  /ui            │
└─────────────────────────────────────┘                  └──────────────────────┘
```

- **kind** — lokalt Kubernetes-kluster i Docker
- **kopf controller** — körs som en Pod inuti klustret
- **prime-api** — körs som en vanlig Docker-container utanför klustret

---

## Steg 0 — Förberedelser

Ladda ner `kind` och `kubectl`, bygg images, starta kluster och API.

```bash
make prereqs   # laddar ner kind + kubectl om de saknas
make build     # docker build för prime-api och prime-controller
make setup     # skapar Docker-nätverk, startar prime-api,
               # skapar kind-klustret och kopplar ihop nätverken
make load      # laddar prime-controller-image in i kind
make deploy    # kubectl apply: namespace, CRD, RBAC, Deployment
```

Verifiera att allt är uppe:

```bash
kubectl cluster-info --context kind-demo-cluster
curl http://localhost:8080/
# → {"status":"ok"}
```

---

## Steg 1 — Installera CRD

CRD:n registrerar den nya typen `PrimeClaim` i API-servern.

```bash
kubectl apply -f manifests/crd.yaml
```

Verifiera att den är registrerad:

```bash
kubectl get crd
kubectl get crd primeclaims.demo.example.com
```

Vänta tills den är `Established`:

```bash
kubectl wait --for=condition=Established \
  crd/primeclaims.demo.example.com --timeout=60s
```

---

## Steg 2 — Utforska CRD:n

Se vilka fält CRD:n definierar:

```bash
kubectl explain primeclaim
kubectl explain primeclaim.spec
kubectl explain primeclaim.status
```

Visa hela CRD-definitionen:

```bash
kubectl describe crd primeclaims.demo.example.com
```

Kubernetes känner nu till typen — men det finns inga objekt ännu:

```bash
kubectl get primeclaims -n demo
# No resources found in demo namespace.
```

---

## CRD:n i detalj

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: primeclaims.demo.example.com   # <plural>.<group>  — unikt namn i klustret
spec:
  group: demo.example.com              # API-grupp  →  apiVersion: demo.example.com/v1
  names:
    kind:      PrimeClaim              # CamelCase — används i YAML-manifester
    plural:    primeclaims             # URL-segment: /apis/demo.example.com/v1/primeclaims
    singular:  primeclaim              # kubectl get primeclaim
    shortNames: [pc]                   # kubectl get pc
  scope: Namespaced                    # Alternativ: Cluster
  versions:
    - name: v1
      served: true                     # API-servern svarar på denna version
      storage: true                    # Versionen som lagras i etcd
      subresources:
        status: {}                     # Separerar spec-skrivning från status-skrivning
```

---

## CRD:n i detalj — schema & kolumner

```yaml
      additionalPrinterColumns:        # Visas i  kubectl get primeclaims
        - name: Requester              # kolumnnamn
          jsonPath: .spec.requester    # värdet hämtas med JSONPath
        - name: Prime
          jsonPath: .status.prime
        - name: Phase
          jsonPath: .status.phase

      schema:
        openAPIV3Schema:
          properties:
            spec:
              required: [requester]    # kubectl apply misslyckas om fältet saknas
              properties:
                requester:
                  type: string
            status:                    # Skrivs av controllern, inte användaren
              properties:
                phase:
                  type: string
                  enum: [Pending, Allocated, Error]  # Validering på serversidan
                prime:
                  type: integer
```

---

## Steg 3 — Starta controllern

Controllern körs som en Deployment i klustret.

```bash
kubectl apply -f manifests/rbac.yaml
kubectl apply -f manifests/controller-deployment.yaml

# Vänta på rollout
kubectl rollout status deployment/prime-controller -n demo
```

Verifiera att Pod:en kör:

```bash
kubectl get pods -n demo
kubectl logs -n demo -l app=prime-controller --tail=20
```

---

## Steg 4 — Applicera första CR

CR:en beskriver önskat tillstånd: *"team-alpha vill ha ett primtal"*.

```bash
cat manifests/samples/prime-alpha.yaml
```
```yaml
apiVersion: demo.example.com/v1
kind: PrimeClaim
metadata:
  name: claim-alpha
  namespace: demo
spec:
  requester: team-alpha
```

```bash
kubectl apply -f manifests/samples/prime-alpha.yaml
```

---

## Steg 5 — Följ upp status

Controllern allokerar primtalet och skriver tillbaka status.

```bash
# Enkel lista
kubectl get primeclaims -n demo

# Bevaka i realtid tills phase = Allocated
kubectl get primeclaims -n demo -w

# Detaljvy med alla fält
kubectl describe primeclaim claim-alpha -n demo
```

Förväntat resultat:

```
NAME          REQUESTER    PHASE       PRIME   AGE
claim-alpha   team-alpha   Allocated   2       5s
```

---

## Steg 6 — Hämta status programmatiskt

Läs enskilda statusfält med JSONPath:

```bash
# Vilket primtal fick claim-alpha?
kubectl get primeclaim claim-alpha -n demo \
  -o jsonpath='{.status.prime}'

# Visa hela status-objektet
kubectl get primeclaim claim-alpha -n demo \
  -o jsonpath='{.status}' | python3 -m json.tool

# YAML-format för full bild
kubectl get primeclaim claim-alpha -n demo -o yaml
```

---

## Steg 7 — Skapa fler claims

Varje ny CR allokerar nästa lediga primtal (2 → 3 → 5 → 7 …).

```bash
kubectl apply -f manifests/samples/prime-beta.yaml
kubectl apply -f manifests/samples/prime-gamma.yaml

# Visa alla tre
kubectl get primeclaims -n demo
```

```
NAME          REQUESTER    PHASE       PRIME   AGE
claim-alpha   team-alpha   Allocated   2       1m
claim-beta    team-beta    Allocated   3       20s
claim-gamma   team-gamma   Allocated   5       8s
```

Kontrollera att externa API:et registrerat dem:

```bash
curl -s http://localhost:8080/primes | python3 -m json.tool
```

---

## Steg 8 — Dashboard i webbläsaren

Öppna det grafiska gränssnittet:

```bash
xdg-open http://localhost:8080/ui
# eller: firefox http://localhost:8080/ui
```

Sidan uppdateras var 3:e sekund och visar:
- Alla primtal 2–311 färgkodade (teal = allokerat, vitt = ledigt)
- Hover över ett allokerat primtal → se ägaren
- Statistikrad: antal allokerade, lediga, nästa tillgängliga

---

## Steg 9 — Radera en CR

Radering frigör primtalet i externa API:et.

```bash
kubectl delete primeclaim claim-beta -n demo
```

Bevaka att objektet försvinner:

```bash
kubectl get primeclaims -n demo -w
```

Verifiera att primtal 3 är ledigt igen:

```bash
curl -s http://localhost:8080/primes | python3 -m json.tool
```

Om en ny claim skapas nu — tilldelas primtal 3 igen.

---

## Steg 10 — Reconciliation loop: simulera drift

Controllern tittar var **10:e sekund** på om primtalet fortfarande finns i API:et.
Öppna UI:t och klicka **Release** på en allokerad rad — primtalet försvinner direkt.

```bash
# Bevaka controllerloggar live i en separat terminal
kubectl logs -n demo -l app=prime-controller -f
```

Vad du ser i loggarna (~10 s efter Release):

```
[WARNING] DRIFT DETECTED: prime 2 for 'team-alpha' is gone from API — healing
[INFO]    Healed: re-allocated prime 2 to 'team-alpha'
```

Kubernetes-objektet ändrades **aldrig** — CR:en sa hela tiden att primtalet skulle finnas.
Controllern märkte avvikelsen och återställde faktiskt tillstånd.

---

## Flödet i detalj — drift & healing

```
[UI] Klicka Release på prime 2
        │
        ▼
  DELETE http://prime-api:8080/primes/2   (direkt, utan kubectl)
        │  PrimeClaim claim-alpha är ORÖRD i etcd
        ▼
  kopf on_timer() triggas (var 10 s)
        │
        ▼
  GET /primes → {allocations: [...]}  ← prime 2 saknas!
        │
        ▼
  DRIFT DETECTED — POST /primes {"requester":"team-alpha"}
        │
        ▼
  API svarar: {"prime": 2, ...}
        │
        ▼
  patch.status["prime"] = 2
  patch.status["lastSyncTime"] = <nu>
        │
        ▼
  Faktiskt tillstånd = önskat tillstånd ✓
```

---

## Steg 11 — Controller-loggar

Loggar visar hela händelsekedjan:

```bash
# Följ loggar live
kubectl logs -n demo -l app=prime-controller -f

# Senaste 50 rader
kubectl logs -n demo -l app=prime-controller --tail=50
```

Förväntade logg-rader vid create:
```
Allocating prime for requester 'team-alpha'
Allocated prime 2 to 'team-alpha'
```

Förväntade logg-rader vid delete:
```
Releasing prime 3
Released prime 3
```

---

## Steg 12 — Felsökning

```bash
# Beskriver CR:ens events (kopf skriver Kubernetes-events)
kubectl describe primeclaim claim-alpha -n demo

# Alla events i demo-namespacet
kubectl get events -n demo --sort-by='.lastTimestamp'

# Pod-status för controllern
kubectl get pods -n demo
kubectl describe pod -n demo -l app=prime-controller

# Starta om controllern
kubectl rollout restart deployment/prime-controller -n demo
```

---

## Flödet i detalj — create

```
kubectl apply -f claim-alpha.yaml
        │
        ▼
  API-servern lagrar PrimeClaim i etcd
        │
        ▼  (Watch-ström: {"type":"ADDED", ...})
  kopf anropar on_create(spec, patch, logger)
        │
        ▼
  POST http://prime-api:8080/primes  {"requester":"team-alpha"}
        │
        ▼
  API svarar: {"prime": 2, "requester": "team-alpha"}
        │
        ▼
  patch.status["phase"] = "Allocated"
  patch.status["prime"] = 2
        │
        ▼
  kopf PATCH:ar status tillbaka till API-servern
```

---

## Flödet i detalj — delete

```
kubectl delete primeclaim claim-beta -n demo
        │
        ▼
  API-servern sätter deletionTimestamp (finalizer håller kvar)
        │
        ▼  (Watch-ström: {"type":"MODIFIED", deletionTimestamp: ...})
  kopf anropar on_delete(spec, status, logger)
        │
        ▼
  DELETE http://prime-api:8080/primes/3
        │
        ▼
  kopf tar bort finalizer
        │
        ▼
  Objektet raderas ur etcd
```

---

## Teardown

```bash
# Ta bort alla claims (controllern frigör primtalen)
kubectl delete primeclaims --all -n demo

# Kontrollera att API:et är tomt
curl -s http://localhost:8080/primes | python3 -m json.tool

# Riv ner allt
make teardown
# → raderar kind-klustret, prime-api-containern och Docker-nätverket
```

---

## Snabbreferens — alla kommandon

```bash
# Setup
make prereqs && make build && make setup && make load && make deploy

# Utforska
kubectl get crd
kubectl explain primeclaim.spec
kubectl get primeclaims -n demo

# Skapa
kubectl apply -f manifests/samples/prime-alpha.yaml

# Bevaka
kubectl get primeclaims -n demo -w
kubectl logs -n demo -l app=prime-controller -f

# Felsök
kubectl describe primeclaim <namn> -n demo
kubectl get events -n demo --sort-by='.lastTimestamp'

# Radera
kubectl delete primeclaim <namn> -n demo

# Teardown
make teardown
```

---

<!-- _class: lead -->

## Sammanfattning

| Byggsten | Roll |
|---|---|
| **CRD** | Registrerar `PrimeClaim` som giltig typ i API-servern |
| **CR** | En instans — det önskade tillståndet (`requester: team-alpha`) |
| **kopf** | Python-framework som kopplar Watch-events till handlers |
| **Controller** | Allokerar/frigör primtal mot externa API:et |
| **Timer** | Kör var 10 s, detekterar drift och healar automatiskt |
| **Status** | Speglar faktiskt tillstånd (`prime: 2`) tillbaka i Kubernetes |

> Kubernetes blir ett **enhetligt kontrollplan** — inte bara för containers.
