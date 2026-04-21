import os
import datetime
import kopf
import httpx

PRIME_API_URL = os.environ.get("PRIME_API_URL", "http://prime-api:8080")


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _api_url(path: str) -> str:
    return f"{PRIME_API_URL}{path}"


# ---------------------------------------------------------------------------
# CREATE — allocate next available prime
# ---------------------------------------------------------------------------
@kopf.on.create("demo.example.com", "v1", "primeclaims")
def on_create(spec, patch, logger, **kwargs):
    requester = spec["requester"]
    logger.info(f"Allocating prime for requester '{requester}'")
    try:
        resp = httpx.post(
            _api_url("/primes"), json={"requester": requester}, timeout=10
        )
        resp.raise_for_status()
    except httpx.RequestError as exc:
        logger.warning(f"Network error: {exc}")
        patch.status["phase"] = "Error"
        patch.status["error"] = str(exc)
        patch.status["lastSyncTime"] = _now()
        raise kopf.TemporaryError(str(exc), delay=15)

    data = resp.json()
    patch.status["phase"] = "Allocated"
    patch.status["prime"] = data["prime"]
    patch.status["lastSyncTime"] = _now()
    patch.status["error"] = ""
    logger.info(f"Allocated prime {data['prime']} to '{requester}'")


# ---------------------------------------------------------------------------
# TIMER — detect drift every 10 s and heal
# ---------------------------------------------------------------------------
@kopf.on.timer("demo.example.com", "v1", "primeclaims", interval=10.0, initial_delay=5.0)
def on_timer(spec, status, patch, logger, **kwargs):
    prime = status.get("prime")
    if not prime or status.get("phase") != "Allocated":
        return

    requester = spec["requester"]

    try:
        resp = httpx.get(_api_url("/primes"), timeout=10)
        resp.raise_for_status()
    except httpx.RequestError as exc:
        logger.warning(f"Drift check skipped — cannot reach API: {exc}")
        return

    allocated = {a["prime"] for a in resp.json()["allocations"]}

    if prime not in allocated:
        logger.warning(
            f"DRIFT DETECTED: prime {prime} for '{requester}' is gone from API — healing"
        )
        try:
            resp = httpx.post(
                _api_url("/primes"), json={"requester": requester}, timeout=10
            )
            resp.raise_for_status()
        except httpx.RequestError as exc:
            patch.status["phase"] = "Error"
            patch.status["error"] = str(exc)
            patch.status["lastSyncTime"] = _now()
            raise kopf.TemporaryError(str(exc), delay=15)

        data = resp.json()
        patch.status["phase"] = "Allocated"
        patch.status["prime"] = data["prime"]
        patch.status["lastSyncTime"] = _now()
        patch.status["error"] = ""
        logger.info(
            f"Healed: re-allocated prime {data['prime']} to '{requester}'"
        )
    else:
        logger.debug(f"Drift check OK: prime {prime} still held by '{requester}'")


# ---------------------------------------------------------------------------
# DELETE — release the prime back to the pool
# ---------------------------------------------------------------------------
@kopf.on.delete("demo.example.com", "v1", "primeclaims")
def on_delete(spec, status, patch, logger, **kwargs):
    prime = status.get("prime")
    if not prime:
        logger.info("No prime in status; nothing to release")
        return

    logger.info(f"Releasing prime {prime}")
    try:
        resp = httpx.delete(_api_url(f"/primes/{prime}"), timeout=10)
        if resp.status_code == 404:
            logger.info("Prime already released — safe to ignore")
        else:
            resp.raise_for_status()
    except httpx.RequestError as exc:
        logger.warning(f"Network error during release: {exc}")
        raise kopf.TemporaryError(str(exc), delay=15)

    logger.info(f"Released prime {prime}")
