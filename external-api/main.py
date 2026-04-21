from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Prime Number Reservation API")

# Registry of allocated primes: prime -> requester
allocations: dict[int, str] = {}


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True


def next_available_prime() -> int:
    candidate = 2
    while candidate in allocations:
        candidate += 1
        while not is_prime(candidate):
            candidate += 1
    return candidate


class AllocateRequest(BaseModel):
    requester: str


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/primes")
def list_allocations():
    return {
        "allocations": [
            {"prime": p, "requester": r}
            for p, r in sorted(allocations.items())
        ]
    }


@app.post("/primes", status_code=201)
def allocate_prime(req: AllocateRequest):
    prime = next_available_prime()
    allocations[prime] = req.requester
    return {"prime": prime, "requester": req.requester}


@app.delete("/primes/{prime}", status_code=204)
def release_prime(prime: int):
    if prime not in allocations:
        raise HTTPException(status_code=404, detail="Prime not allocated")
    del allocations[prime]


@app.get("/ui", response_class=HTMLResponse)
def ui():
    return _UI_HTML


_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lumon Industries — Prime Allocation Registry</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --lumon:      #00857a;
  --lumon-dark: #006B62;
  --lumon-pale: #e6f4f3;
  --bg:         #edeae4;
  --surface:    #f8f6f2;
  --white:      #ffffff;
  --border:     #ccc9c0;
  --border-lt:  #e0ddd6;
  --text:       #1c1c1a;
  --text-mid:   #5a5a56;
  --text-dim:   #9a9a94;
  --warn:       #c0392b;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'DM Sans', Helvetica, Arial, sans-serif;
  font-size: 14px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Header ─────────────────────────────────────── */
header {
  background: var(--white);
  border-bottom: 3px solid var(--lumon);
  padding: 0 48px;
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  min-height: 72px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 0;
}

.lumon-mark {
  width: 40px;
  height: 40px;
  background: var(--lumon);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.lumon-mark svg {
  width: 22px;
  height: 22px;
  fill: white;
}

.header-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.company-name {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--lumon-dark);
  text-transform: uppercase;
}

.dept-name {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.20em;
  color: var(--text-mid);
  text-transform: uppercase;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 16px 0;
}

.header-meta {
  text-align: right;
}

.meta-label {
  font-size: 9px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 3px;
}

.meta-val {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}

.sync-badge {
  display: flex;
  align-items: center;
  gap: 7px;
  background: var(--lumon-pale);
  border: 1px solid var(--lumon);
  color: var(--lumon-dark);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  padding: 6px 14px;
}

.sync-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--lumon);
  animation: pulse 2s infinite;
}

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.25} }

/* ── Notice bar ──────────────────────────────────── */
.notice {
  background: var(--lumon-pale);
  border-bottom: 1px solid var(--lumon);
  padding: 9px 48px;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--lumon-dark);
  text-align: center;
  text-transform: uppercase;
}

/* ── Main ────────────────────────────────────────── */
main {
  flex: 1;
  padding: 36px 48px;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
}

/* ── Stat cards ──────────────────────────────────── */
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  margin-bottom: 36px;
}

.stat {
  background: var(--white);
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat-label {
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--text-dim);
}

.stat-val {
  font-size: 36px;
  font-weight: 300;
  color: var(--lumon-dark);
  line-height: 1;
}

.stat-sub {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 0.08em;
}

/* ── Section ─────────────────────────────────────── */
.section {
  margin-bottom: 36px;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--text-mid);
}

.section-note {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 0.08em;
}

/* ── Prime grid ──────────────────────────────────── */
.prime-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(54px, 1fr));
  gap: 4px;
}

.cell {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 500;
  position: relative;
  cursor: default;
  transition: background .1s;
  border: 1px solid;
}

.cell.free {
  background: var(--white);
  border-color: var(--border-lt);
  color: var(--text-mid);
}

.cell.free:hover {
  background: var(--lumon-pale);
  border-color: var(--lumon);
  color: var(--lumon-dark);
}

.cell.used {
  background: var(--lumon);
  border-color: var(--lumon-dark);
  color: var(--white);
}

.cell.used:hover {
  background: var(--lumon-dark);
}

.cell .tip {
  display: none;
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--text);
  color: var(--white);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.08em;
  padding: 4px 10px;
  white-space: nowrap;
  z-index: 20;
  pointer-events: none;
}

.cell.used:hover .tip { display: block; }

/* ── Table ───────────────────────────────────────── */
.reg-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--white);
  border: 1px solid var(--border);
}

.reg-table th {
  text-align: left;
  padding: 10px 16px;
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--text-dim);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.reg-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-lt);
  vertical-align: middle;
}

.reg-table tbody tr:last-child td { border-bottom: none; }

.reg-table tbody tr:hover td { background: var(--lumon-pale); }

.prime-num {
  font-size: 20px;
  font-weight: 300;
  color: var(--lumon-dark);
}

.req-name {
  font-weight: 500;
  color: var(--text);
}

.status-chip {
  display: inline-block;
  padding: 3px 10px;
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  background: var(--lumon-pale);
  color: var(--lumon-dark);
  border: 1px solid var(--lumon);
}

.empty-row td {
  text-align: center;
  padding: 36px;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-dim);
}

.release-btn {
  background: none;
  border: 1px solid var(--warn);
  color: var(--warn);
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  padding: 4px 12px;
  cursor: pointer;
}

.release-btn:hover {
  background: var(--warn);
  color: var(--white);
}

.drift-banner {
  display: none;
  background: #fff3f2;
  border: 1px solid var(--warn);
  color: var(--warn);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 10px 20px;
  margin-bottom: 20px;
  text-align: center;
}

/* ── Footer ──────────────────────────────────────── */
footer {
  background: var(--white);
  border-top: 1px solid var(--border);
  padding: 14px 48px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--text-dim);
  text-transform: uppercase;
}

.footer-lumon { color: var(--lumon-dark); font-weight: 500; }
</style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="lumon-mark">
      <!-- Simplified L mark -->
      <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <rect x="5" y="4" width="4" height="16"/>
        <rect x="5" y="16" width="14" height="4"/>
      </svg>
    </div>
    <div class="header-titles">
      <div class="company-name">Lumon Industries</div>
      <div class="dept-name">Macro Data Refinement &nbsp;·&nbsp; Prime Allocation Registry</div>
    </div>
  </div>
  <div class="header-right">
    <div class="header-meta">
      <div class="meta-label">Last Updated</div>
      <div class="meta-val" id="ts">—</div>
    </div>
    <div class="sync-badge">
      <div class="sync-dot"></div>
      <span>Live Sync</span>
    </div>
  </div>
</header>

<div class="notice">
  All prime numbers are the property of Lumon Industries.
  Allocation of numbers outside approved workflows is a terminable offense.
</div>

<main>
  <div class="drift-banner" id="drift-banner">
    &#9888; Drift introduced — prime released outside Kubernetes. Waiting for controller to heal...
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-label">Allocated</div>
      <div class="stat-val" id="n-used">0</div>
      <div class="stat-sub">Numbers in active use</div>
    </div>
    <div class="stat">
      <div class="stat-label">Available</div>
      <div class="stat-val" id="n-free">—</div>
      <div class="stat-sub">Numbers in pool</div>
    </div>
    <div class="stat">
      <div class="stat-label">Next Available</div>
      <div class="stat-val" id="next">—</div>
      <div class="stat-sub">Pending assignment</div>
    </div>
  </div>

  <div class="section">
    <div class="section-head">
      <div class="section-title">Prime Number Pool</div>
      <div class="section-note" id="pool-note">Primes 2 – 311 &nbsp;·&nbsp; hover allocated for owner</div>
    </div>
    <div class="prime-grid" id="grid"></div>
  </div>

  <div class="section">
    <div class="section-head">
      <div class="section-title">Allocation Register</div>
      <div class="section-note">Current assignments by refinement unit</div>
    </div>
    <table class="reg-table">
      <thead>
        <tr>
          <th>Entry</th>
          <th>Prime</th>
          <th>Refinement Unit</th>
          <th>Status</th>
          <th>Simulate Drift</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</main>

<footer>
  <span>
    <span class="footer-lumon">Lumon Industries</span>
    &nbsp;·&nbsp; Prime Resource Management System &nbsp;·&nbsp; Internal Use Only
  </span>
  <span>Kubernetes Controller Interface</span>
</footer>

<script>
function sieve(max) {
  const s = new Uint8Array(max + 1).fill(1);
  s[0] = s[1] = 0;
  for (let i = 2; i * i <= max; i++)
    if (s[i]) for (let j = i * i; j <= max; j += i) s[j] = 0;
  return [...Array(max + 1).keys()].filter(i => s[i]);
}

const POOL = sieve(311);

function fmtDate(d) {
  return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
}

async function refresh() {
  try {
    const data = await fetch('/primes').then(r => r.json());
    const used = {};
    for (const a of data.allocations) used[a.prime] = a.requester;

    const nUsed = data.allocations.length;
    const nFree = POOL.filter(p => !used[p]).length;
    const next  = POOL.find(p => !used[p]) ?? '—';

    document.getElementById('n-used').textContent = nUsed;
    document.getElementById('n-free').textContent = nFree;
    document.getElementById('next').textContent   = next;
    document.getElementById('ts').textContent     = fmtDate(new Date());

    // Grid
    const grid = document.getElementById('grid');
    grid.innerHTML = '';
    for (const p of POOL) {
      const div = document.createElement('div');
      div.className = 'cell ' + (used[p] ? 'used' : 'free');
      div.textContent = p;
      if (used[p]) {
        const tip = document.createElement('div');
        tip.className = 'tip';
        tip.textContent = used[p];
        div.appendChild(tip);
      }
      grid.appendChild(div);
    }

    // Table
    const tbody = document.getElementById('tbody');
    if (!data.allocations.length) {
      tbody.innerHTML =
        '<tr class="empty-row"><td colspan="4">No active allocations</td></tr>';
    } else {
      tbody.innerHTML = [...data.allocations]
        .sort((a, b) => a.prime - b.prime)
        .map((a, i) => `<tr>
          <td style="color:var(--text-dim);font-size:12px">${String(i + 1).padStart(3, '0')}</td>
          <td><span class="prime-num">${a.prime}</span></td>
          <td><span class="req-name">${a.requester}</span></td>
          <td><span class="status-chip">Allocated</span></td>
          <td><button class="release-btn" onclick="releaseManually(${a.prime})">Release</button></td>
        </tr>`).join('');
    }
  } catch(e) { console.error(e); }
}

async function releaseManually(prime) {
  if (!confirm(`Release prime ${prime} directly from the API — bypassing Kubernetes?\\nThe controller should detect drift and re-allocate within ~10 seconds.`)) return;
  try {
    await fetch('/primes/' + prime, { method: 'DELETE' });
    document.getElementById('drift-banner').style.display = 'block';
    setTimeout(() => {
      document.getElementById('drift-banner').style.display = 'none';
    }, 15000);
    await refresh();
  } catch(e) { console.error(e); }
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>"""
