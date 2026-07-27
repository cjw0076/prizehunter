#!/usr/bin/env python3
"""prizehunterd — the PrizeHunter service daemon + web cockpit.

founder 2026-07-23: "실서비스 배포 · daemon 형태 · IDE 같은 native app이 필요한가?"
DECISION: daemon + WEB cockpit (not a native app). The human's job here is supervise / confirm / unlock /
steer — not edit code (agents do that). A browser cockpit needs zero install, works anywhere, and can later
become hosted SaaS; a native shell (Tauri) can wrap this same page later if desired — it is not the core.

Two things in one process, no third-party deps (stdlib only, so it runs on any user's box):
  • LOOP    — every --interval seconds runs tools/autopush.sh (type-aware self-push: leaderboard drives
              continuously, submission crafts once then waits for confirm) so the system never idles.
  • COCKPIT — serves one page: the type-aware board, live drives, the CONFIRM QUEUE (what needs the founder),
              and the COMPOUNDING lever library (what the system has learned, per task-type).

  python3 tools/prizehunterd.py [--port 8787] [--interval 900] [--no-loop] [--once]

State is the same plain files the CLI uses (single source of truth, nothing hidden in the daemon):
  .runs/autopush_board.tsv · .runs/fleet_workers.tsv · LEVER_LIBRARY.tsv · .runs/autopush_last.log
"""
import argparse, hashlib, hmac, html, http.cookies, json, os, re, secrets, shutil, subprocess, sys, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.environ.get("PH_RUNS") or os.path.join(CT, ".runs")
os.makedirs(R, exist_ok=True)  # fresh install has no .runs yet; token minting must not crash
BOARD = os.path.join(R, "autopush_board.tsv")
WORKERS = os.path.join(R, "fleet_workers.tsv")
LIB = os.path.join(CT, "LEVER_LIBRARY.tsv")
LASTLOG = os.path.join(R, "autopush_last.log")
AUTOPUSH = os.path.join(CT, "tools", "autopush.sh")
CONFIRMS = os.path.join(R, "confirm_log.jsonl")   # append-only: what the founder acknowledged, never destructive
TOKENF = os.path.join(R, "cockpit_token")         # gitignored; 0600


# ---------- auth (real service: the cockpit can trigger drives and record confirms, so it is never open) ----------
def load_token():
    """One long random token per install. Created on first run with 0600, printed once at startup.
    Override with PH_COCKPIT_TOKEN (e.g. injected by a supervisor / container secret)."""
    t = os.environ.get("PH_COCKPIT_TOKEN")
    if t:
        return t.strip()
    try:
        if os.stat(TOKENF).st_mode & 0o077:
            os.chmod(TOKENF, 0o600)  # heal a loose pre-existing file before trusting it
        t = open(TOKENF).read().strip()
        if t:
            return t
    except OSError:
        pass
    t = secrets.token_urlsafe(32)
    fd = os.open(TOKENF, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(t + "\n")
    os.chmod(TOKENF, 0o600)  # O_TRUNC keeps a pre-existing file's old mode; force 0600
    return t


TOKEN = load_token()
COOKIE = "ph_cockpit"
PLOG = os.path.join(CT, "PROCESS_LOG.tsv")
TENANTS_F = os.path.join(R, "tenants.json")


# ---------- MULTI-TENANCY: one daemon, isolated tenants (founder 2026-07-25 "멀티테넌트로 가") ----------
# Each tenant gets its OWN board / workers / confirm ledger / lever library / process log, so competitions,
# scores and learned levers never leak between users. Tokens are stored HASHED (sha256) — the plaintext token
# is shown exactly once at creation. The pre-existing single-user install becomes tenant 'default' with its
# current paths, so nothing has to be migrated.
def _sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def save_tenants(d):
    fd = os.open(TENANTS_F, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(d, f, indent=1)


def load_tenants():
    try:
        d = json.load(open(TENANTS_F))
        if d:
            return d
    except Exception:
        pass
    d = {"default": {"name": "default", "token_sha256": _sha(TOKEN),
                     "created": time.strftime("%FT%TZ", time.gmtime())}}
    save_tenants(d)
    return d


def add_tenant(name):
    d = load_tenants()
    tid = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")[:32] or ("t" + secrets.token_hex(3))
    while tid in d:
        tid += secrets.token_hex(1)
    tok = secrets.token_urlsafe(32)
    d[tid] = {"name": name, "token_sha256": _sha(tok), "created": time.strftime("%FT%TZ", time.gmtime())}
    save_tenants(d)
    pp = paths(tid)
    if not os.path.exists(pp["board"]):
        with open(pp["board"], "w") as f:
            f.write("# key\ttype\tdir\tbest\ttarget\tworker_cmd\tsubmit_action\tstatus\n")
    return tid, tok


def paths(tid):
    """Tenant-scoped state paths. 'default' keeps the original single-user layout (no migration)."""
    if tid == "default":
        return {"runs": R, "board": BOARD, "workers": WORKERS, "lib": LIB, "plog": PLOG,
                "lastlog": LASTLOG, "confirms": CONFIRMS}
    base = os.path.join(R, "tenants", tid)
    os.makedirs(base, exist_ok=True)
    j = lambda n: os.path.join(base, n)
    return {"runs": base, "board": j("autopush_board.tsv"), "workers": j("fleet_workers.tsv"),
            "lib": j("LEVER_LIBRARY.tsv"), "plog": j("PROCESS_LOG.tsv"),
            "lastlog": j("autopush_last.log"), "confirms": j("confirm_log.jsonl")}


def resolve_tenant(token):
    """token -> tenant id (constant-time compare against stored hashes), or None."""
    if not token:
        return None
    h = _sha(token)
    found = None
    for tid, t in load_tenants().items():
        if hmac.compare_digest(t.get("token_sha256", ""), h) and found is None:
            found = tid
    return found  # always walks every tenant so timing cannot leak match position (QA 2026-07-28)

LOGIN = """<!doctype html><meta charset=utf-8><title>PrizeHunter — 로그인</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#fbfbfa;color:#191917;
font:14px/1.6 ui-sans-serif,system-ui,sans-serif}@media(prefers-color-scheme:dark){body{background:#141414;color:#ededea}}
form{border:1px solid #d9d9d5;border-radius:12px;padding:22px 24px;max-width:340px}
@media(prefers-color-scheme:dark){form{border-color:#2b2b28}}
h1{font-size:16px;margin:0 0 4px}p{color:#6b6b66;font-size:12.5px;margin:0 0 14px}
input,button{font:inherit;width:100%;padding:8px 10px;border-radius:7px;border:1px solid #d9d9d5;background:transparent;color:inherit}
button{margin-top:9px;background:#1f6f4a;border-color:#1f6f4a;color:#fff;cursor:pointer}</style>
<form method=GET action="/"><h1>PrizeHunter cockpit</h1>
<p>액세스 토큰을 입력하세요. (daemon 시작 로그 또는 <code>.runs/cockpit_token</code>)</p>
<input name=t type=password placeholder="토큰" autofocus autocomplete=off>
<button>들어가기</button></form>"""


# ---------- state readers (plain files; the CLI and the cockpit see the same truth) ----------
def _rows(path):
    try:
        with open(path) as f:
            return [l.rstrip("\n").split("\t") for l in f
                    if l.strip() and not l.startswith("#")]
    except OSError:
        return []


REG = os.path.join(CT, "portfolio_registry.tsv")


def _reg_rows():
    """SINGLE SOURCE OF TRUTH for the default tenant: portfolio_registry.tsv (all live competitions).
    The cockpit used to read only the hand-made 12-row board, so 50 of 62 competitions were INVISIBLE — which is
    how the head agent concluded 'nothing to drive' while real headroom sat unseen (SYSTEM_GAP_REPORT #2)."""
    cols, out = [], []
    try:
        for l in open(REG):
            if l.startswith("#   ") and l[4:5].isalpha() and len(l.split()) > 1:
                cols.append(l.split()[1])
            elif not l.startswith("#"):
                break
        g = lambda f, n: f[cols.index(n)] if n in cols and cols.index(n) < len(f) else ""
        for l in open(REG):
            if l.startswith("#") or not l.strip():
                continue
            f = l.rstrip("\n").split("\t")
            if g(f, "key") in ("key", ""):    # the registry carries a literal header row; it is not a competition
                continue
            st = g(f, "status")
            if st in ("lapsed", "settled", "dropped"):
                continue
            metric = g(f, "metric")
            typ = "submission" if metric in ("n/a", "", "-") else "leaderboard"
            out.append({"key": g(f, "key"), "type": typ, "dir": g(f, "direction") or "max",
                        "best": g(f, "best") or "-", "target": g(f, "rank1") or "-",
                        "worker_cmd": "", "submit": "-", "status": st})
    except Exception:
        pass
    return out


def board(P=None):
    P = P or paths("default")
    legacy = []
    for r in _rows(P["board"]):
        r = (r + [""] * 8)[:8]
        legacy.append(dict(zip(("key", "type", "dir", "best", "target", "worker_cmd", "submit", "status"), r)))
    if P["board"] != BOARD:          # a non-default tenant has only its own board
        return legacy
    reg = _reg_rows()
    if not reg:
        return legacy
    lmap = {r["key"]: r for r in legacy}
    for r in reg:                    # overlay the legacy board's wiring (worker_cmd / submit action) when present
        l = lmap.get(r["key"])
        if l:
            r["worker_cmd"] = l.get("worker_cmd", "")
            r["submit"] = l.get("submit", "-")
            if l.get("status"):
                r["status"] = l["status"]
    known = {r["key"] for r in reg}
    return reg + [l for l in legacy if l["key"] not in known]


def drives(P=None):
    live = {}
    for r in _rows((P or paths("default"))["workers"]):
        if len(r) < 2 or not r[0].startswith("drive:"):
            continue
        key, pid = r[0][6:], r[1]
        try:
            os.kill(int(pid), 0)
            live[key] = {"pid": pid, "log": r[2] if len(r) > 2 else ""}
        except (OSError, ValueError):
            pass
    return live


def levers(P=None):
    out = []
    for r in _rows((P or paths("default"))["lib"]):
        r = (r + [""] * 9)[:9]
        out.append(dict(zip(("task_type", "comp", "before", "after", "delta", "dir", "lever", "calib", "date"), r)))
    return out


def confirmed_keys(P=None):
    """Acks are recorded per (key, value) — so a LATER improvement on the same competition surfaces again
    instead of being silently swallowed by an old acknowledgement."""
    seen = set()
    try:
        with open((P or paths("default"))["confirms"]) as f:
            for l in f:
                try:
                    d = json.loads(l)
                    seen.add((d.get("key"), str(d.get("value", ""))))
                except Exception:
                    pass
    except OSError:
        pass
    return seen


def pendings(P=None):
    """Pending confirms are FILES (.runs/confirm_<key>.pending: value \\t action \\t at) — independent of the
    board's drive status, so a leaderboard keeps climbing while an earlier improvement awaits confirmation."""
    out = {}
    try:
        for fn in os.listdir((P or paths("default"))["runs"]):
            m = re.fullmatch(r"confirm_(.+)\.pending", fn)
            if not m:
                continue
            parts = (open(os.path.join((P or paths("default"))["runs"], fn)).read().strip().split("\t") + ["", "", ""])[:3]
            out[m.group(1)] = {"value": parts[0], "action": parts[1], "at": parts[2]}
    except OSError:
        pass
    return out


def state(tid="default"):
    P = paths(tid)
    b, d, ack, pend = board(P), drives(P), confirmed_keys(P), pendings(P)
    for row in b:
        row["live"] = row["key"] in d
        row["pid"] = d.get(row["key"], {}).get("pid", "")
        p = pend.get(row["key"])
        row["acked"] = bool(p) and (row["key"], str(p["value"])) in ack
        row["pending"] = bool(p) and not row["acked"]
        if p:
            row["pending_value"] = p["value"]
            row["pending_action"] = p["action"]
    lv = levers(P)
    by_type = {}
    for l in lv:
        by_type.setdefault(l["task_type"], []).append(l)
    try:
        last = open(P["lastlog"]).read()[-4000:]
    except OSError:
        last = "(autopush 미실행)"
    # SPINE: the resonance loop's gate state is part of the dashboard — a loop nobody can see is a loop nobody runs
    res = {"open": "", "rounds": 0}
    try:
        oc = os.path.join(P["runs"], "resonance_open_commitment.txt")
        res["open"] = open(oc).read().strip() if os.path.exists(oc) else ""
        rl = os.path.join(CT, "RESONANCE_LOG.md")
        if os.path.exists(rl):
            t = open(rl).read()
            res["rounds"] = t.count("\n## ")
            res["commitments"] = t.count("### COMMITMENT")
            res["closed"] = t.count("### OUTCOME")
    except Exception:
        pass
    return {
        "resonance": res,
        "tenant": load_tenants().get(tid, {}).get("name", tid),
        "board": b,
        "levers_by_type": by_type,
        "n_levers": len(lv),
        "confirm_queue": [r for r in b if r.get("pending")],
        "last_cycle": last,
        "load": (open("/proc/loadavg").read().split()[0] if os.path.exists("/proc/loadavg") else "?"),
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------- Layer B readers (files are the only source of truth; nothing here mutates state) ----------
def _reg_cols():
    cols = []
    try:
        for l in open(REG):
            if l.startswith("#   ") and l[4:5].isalpha() and len(l.split()) > 1: cols.append(l.split()[1])
            elif not l.startswith("#"): break
    except OSError: pass
    return cols


def api_portfolio():
    """Every live competition with the fields a dashboard needs. Registry = single source of truth."""
    cols = _reg_cols(); out = []
    g = lambda f, n: f[cols.index(n)] if n in cols and cols.index(n) < len(f) else ""
    try:
        for l in open(REG):
            if l.startswith("#") or not l.strip(): continue
            f = l.rstrip("\n").split("\t")
            if g(f, "key") in ("key", ""): continue
            st = g(f, "status")
            out.append({"key": g(f, "key"), "status": st, "metric": g(f, "metric"),
                        "direction": g(f, "direction"), "best": g(f, "best"), "rank1": g(f, "rank1"),
                        "blocker": g(f, "blocker")[:300], "next_lever": g(f, "next_lever")[:300],
                        "live": st not in ("lapsed", "settled", "dropped")})
    except OSError: pass
    return {"count": len(out), "live": sum(1 for r in out if r["live"]), "rows": out}


def api_fleet(tid="default"):
    """Substrate availability/cooling + live drives + box load — the resource question, as JSON."""
    P = paths(tid); subs = {}
    for name in ("codex", "agy", "claude", "ollama"):
        bo = os.path.join(R, f".substrate_backoff.{name}")
        cool = None
        if os.path.exists(bo):
            try: cool = int(time.time() - os.path.getmtime(bo))
            except OSError: cool = None
        subs[name] = {"present": bool(shutil.which(name)), "cooling_s": cool}
    return {"substrates": subs, "drives": drives(P),
            "load": (open("/proc/loadavg").read().split()[:3] if os.path.exists("/proc/loadavg") else []),
            "note": "judge/refute roles deliberately exclude the local substrate (it produced a hallucinated FAIL)"}


def api_gates(tid="default"):
    """What is waiting on the human. NOTE: this endpoint is READ-ONLY by design — see the POST /api/ack comment."""
    P = paths(tid); pend = pendings(P); ack = confirmed_keys(P)
    blocked = []
    try:
        for fn in os.listdir(P["runs"]):
            m = re.fullmatch(r"confirm_(.+)\.blocked", fn)
            if m:
                parts = (open(os.path.join(P["runs"], fn)).read().strip().split("\t") + ["", ""])[:2]
                blocked.append({"key": m.group(1), "value": parts[0], "reason": parts[1][:300]})
    except OSError: pass
    return {"pending": [{"key": k, **v, "acked": (k, str(v.get("value"))) in ack} for k, v in pend.items()],
            "transfer_blocked": blocked,
            "external_submit_policy": "An external submission is NEVER fired from the web surface. It requires "
                                      "`ph preflight confirm <key>` at a TTY (rule checklist + literal 'I CONFIRM' "
                                      "+ artifact fingerprint). The spec's POST /api/action/approve is intentionally "
                                      "NOT implemented as a submit trigger — a click cannot carry that liability."}


def campaign_dir(key):
    """Registry-first campaign resolution, shared with gap_view (the registry IS the source of truth for the
    key→dir mapping; keys and dir names diverge by design). The previous local heuristic — first campaign dir
    containing the longest token — resolved `rogii-wellbore-geology` to an empty same-named sibling, so the
    cockpit was showing a blank record for our most active competition."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from gap_view import resolve_dir
        return resolve_dir(key)
    except Exception:
        camp = os.path.join(CT, "campaigns")
        if os.path.isdir(os.path.join(camp, key)):
            return os.path.join(camp, key)
        try:
            toks = [t for t in re.split(r"[-_]", key) if t and not t.isdigit()]
            tok = max(toks, key=len) if toks else key
            for dd in sorted(os.listdir(camp)):
                if tok and tok in dd:
                    return os.path.join(camp, dd)
        except OSError:
            pass
        return None


def api_campaign(key):
    """One competition's own record: the heads of its frame/gap/worklog plus its recorded score history."""
    key = re.sub(r"[^A-Za-z0-9._-]", "", key)[:80]
    d = campaign_dir(key)
    def head(fn, n=1800):
        try: return open(os.path.join(d, fn), errors="ignore").read()[:n]
        except Exception: return ""
    hist = []
    try: hist = json.load(open(os.path.join(R, f"goal_{key}.json"))).get("history", [])
    except Exception: pass
    vw = os.path.join(d, "VIEW", "index.html") if d else ""
    return {"key": key, "dir": (d or "").replace(CT + "/", ""), "history": hist,
            "frame": head("FRAME.md"), "gap": head("GAP_REPORT.md"), "worklog": head("WORKLOG.md"),
            "submit_guide": head("SUBMIT_GUIDE.md"),
            # the rendered geometry (ph view). The founder's eye is the only cure for Geometry Blindness,
            # so the cockpit must be able to SHOW it, not just link to a path on a box they are not on.
            "view": {"exists": bool(vw and os.path.isfile(vw)),
                     "at": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(vw)))
                            if vw and os.path.isfile(vw) else ""),
                     "url": "view/%s" % key,
                     "findings": head("VIEW/FINDINGS.md", 2400)}}


def api_view_html(key):
    """Serve a campaign's rendered VIEW page. Read-only; renders nothing itself (run `ph view <key>` to build)."""
    key = re.sub(r"[^A-Za-z0-9._-]", "", key)[:80]
    d = campaign_dir(key)
    p = os.path.join(d, "VIEW", "index.html") if d else ""
    if p and os.path.isfile(p):
        try:
            return open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            pass
    return ("<!doctype html><meta charset=utf-8><body style=\"font:14px system-ui;padding:32px\">"
            "<h2>no rendered view for <code>%s</code></h2><p>Build it on the box that holds the data:</p>"
            "<pre>ph view %s</pre><p style=\"opacity:.7\">It writes VIEW/index.html + VIEW/FINDINGS.md into "
            "the campaign directory; this page then serves it.</p>" % (html.escape(key), html.escape(key)))


# ---------- the self-push loop ----------
def cycle(tid="default"):
    """One autopush cycle for ONE tenant (type-aware: leaderboard=continuous, submission=once-then-confirm).
    Tenant isolation is passed to the shell tools through PH_* env overrides."""
    P = paths(tid)
    env = dict(os.environ, PH_RUNS=P["runs"], PH_BOARD=P["board"], PH_WORKERS=P["workers"],
               PH_LIB=P["lib"], PH_PLOG=P["plog"])
    try:
        p = subprocess.run(["bash", AUTOPUSH], capture_output=True, text=True, timeout=600,
                           cwd=os.path.dirname(CT), env=env)
        out = "\n".join(l for l in (p.stdout + p.stderr).splitlines() if "libtinfo" not in l)
    except Exception as e:
        out = f"autopush failed: {e!r}"
    try:
        with open(P["lastlog"], "w") as f:
            f.write(out)
    except OSError:
        pass
    return out


def loop(interval):
    while True:
        for tid in load_tenants():          # every tenant gets its own self-push cycle
            cycle(tid)
        time.sleep(interval)


# ---------- cockpit ----------
PAGE = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>PrizeHunter — cockpit</title><style>
*{box-sizing:border-box}:root{--bg:#fbfbfa;--fg:#191917;--mut:#6b6b66;--line:#e4e4e0;--card:#fff;--accent:#1f6f4a;--warn:#b45309;--bad:#b91c1c}
@media(prefers-color-scheme:dark){:root{--bg:#141414;--fg:#ededea;--mut:#9a9a94;--line:#2b2b28;--card:#1c1c1a;--accent:#4ade80;--warn:#f59e0b;--bad:#f87171}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 ui-sans-serif,-apple-system,"Pretendard",system-ui,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:19px;margin:0;letter-spacing:-.01em}h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin:30px 0 10px;font-weight:600}
header{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:14px}
.sub{color:var(--mut);font-size:12.5px}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:7px;padding:5px 11px;cursor:pointer}
button:hover{border-color:var(--accent)}button.p{background:var(--accent);border-color:var(--accent);color:#fff}
table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;color:var(--mut);font-weight:600;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;padding:6px 8px;border-bottom:1px solid var(--line)}
td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}td.n{text-align:right;font-variant-numeric:tabular-nums}
.card{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:4px 12px 8px;overflow-x:auto}
.pill{display:inline-block;font-size:11px;padding:1.5px 7px;border-radius:99px;border:1px solid var(--line);color:var(--mut)}
.live{color:var(--accent);border-color:var(--accent)}.rdy{color:var(--warn);border-color:var(--warn)}.blk{color:var(--bad);border-color:var(--bad)}
.lv{font-size:12.5px;color:var(--fg);margin:0 0 7px;padding-left:11px;border-left:2px solid var(--accent)}
.lv .d{color:var(--mut);font-variant-numeric:tabular-nums}
pre{font-size:12px;white-space:pre-wrap;color:var(--mut);margin:0;max-height:230px;overflow:auto}
.g{display:grid;gap:14px}@media(min-width:760px){.g2{grid-template-columns:1fr 1fr}}
.k{font-weight:600}.empty{color:var(--mut);font-size:12.5px;padding:8px}
</style></head><body><div class=wrap>
<header><h1>PrizeHunter</h1><span class=sub id=meta></span>
<span style="margin-left:auto;display:flex;gap:8px"><button onclick=push()>지금 push</button><button onclick=load()>새로고침</button></span></header>
<div id=app></div></div><script>
const esc=s=>String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
async function load(){const s=await(await fetch("api/state")).json();render(s)}
async function push(){document.getElementById("meta").textContent="push 중…";await fetch("api/push",{method:"POST"});load()}
async function ack(k){await fetch("api/confirm",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({key:k})});load()}
function render(s){
 document.getElementById("meta").textContent=`load ${s.load} · ${s.n_levers} levers · ${s.ts}`;
 const t=(x)=>x.filter(r=>r.type===arguments[1]);
 const rowsFor=ty=>s.board.filter(r=>r.type===ty);
 const stat=r=>r.live?`<span class="pill live">LIVE ${esc(r.pid)}</span>`:(r.status==="ready"?`<span class="pill rdy">컨펌대기</span>`:(r.type==="blocked"?`<span class="pill blk">게이트</span>`:`<span class=pill>${esc(r.status||"idle")}</span>`));
 let h="";
 h+=`<h2>컨펌 큐 — 당신의 액션이 필요한 것</h2><div class=card>`;
 h+= s.confirm_queue.length? `<table><tr><th>대회</th><th>타입</th><th class=n>검증 결과</th><th>필요 액션</th><th></th></tr>`+
  s.confirm_queue.map(r=>`<tr><td class=k>${esc(r.key)}</td><td>${esc(r.type)}</td><td class=n>${esc(r.pending_value||r.best)}</td><td>${esc(r.pending_action||r.submit)}</td><td><button class=p onclick="ack('${esc(r.key)}')">확인</button></td></tr>`).join("")+`</table>`
  : `<div class=empty>대기 중인 컨펌 없음 — 시스템이 계속 밀고 있습니다.</div>`;
 h+=`</div>`;
 h+=`<h2>리더보드형 — 마감까지 계속 점수 개선</h2><div class=card><table><tr><th>대회</th><th class=n>현재</th><th class=n>목표</th><th>제출 경로</th><th>상태</th></tr>`+
   rowsFor("leaderboard").map(r=>`<tr><td class=k>${esc(r.key)}</td><td class=n>${esc(r.best)}</td><td class=n>${esc(r.target)}</td><td>${esc(r.submit)}</td><td>${stat(r)}</td></tr>`).join("")+`</table></div>`;
 h+=`<h2>제출형 — 1회 제작 후 컨펌 (반복하지 않음)</h2><div class=card><table><tr><th>대회</th><th>산출물</th><th>제출 경로</th><th>상태</th></tr>`+
   rowsFor("submission").map(r=>`<tr><td class=k>${esc(r.key)}</td><td>${esc(r.best)}</td><td>${esc(r.submit)}</td><td>${stat(r)}</td></tr>`).join("")+`</table></div>`;
 const blk=rowsFor("blocked");
 if(blk.length)h+=`<h2>게이트 — 1회 언락하면 자율 드라이브로 승격</h2><div class=card><table>`+
   blk.map(r=>`<tr><td class=k>${esc(r.key)}</td><td>${esc(r.submit)}</td><td>${stat(r)}</td></tr>`).join("")+`</table></div>`;
 h+=`<h2>복리 지능 — 학습한 레버 (task-type별)</h2><div class="g g2">`;
 const ks=Object.keys(s.levers_by_type);
 h+= ks.length? ks.map(k=>`<div class=card><div style="padding:8px 0"><span class=k>${esc(k)}</span> <span class=pill>${s.levers_by_type[k].length}</span></div>`+
    s.levers_by_type[k].map(l=>`<div class=lv>${esc(l.lever).slice(0,300)}<div class=d>${esc(l.comp)}: ${esc(l.before)} → ${esc(l.after)} (Δ${esc(l.delta)})</div></div>`).join("")+`</div>`).join("")
   : `<div class=card><div class=empty>아직 레버 없음 — 첫 드라이브가 라이브러리를 시작합니다.</div></div>`;
 h+=`</div>`;
 h+=`<h2>마지막 자기-푸시 사이클</h2><div class=card><pre>${esc(s.last_cycle)}</pre></div>`;
 document.getElementById("app").innerHTML=h;
}
load();setInterval(load,20000);
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, body, ctype="application/json; charset=utf-8", code=200):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    # ---- auth helpers ----
    def _q(self):
        parts = self.path.split("?", 1)
        return urllib.parse.parse_qs(parts[1]) if len(parts) > 1 else {}

    def _authed(self):
        """Resolve the request's TENANT from a session cookie, Authorization: Bearer, or ?t=<token>.
        Sets self.tid and self.tok. Returns False when no tenant matches (constant-time hash compare)."""
        self.tid = self.tok = None
        c = http.cookies.SimpleCookie(self.headers.get("Cookie") or "")
        cand = []
        if COOKIE in c:
            cand.append(c[COOKIE].value)
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            cand.append(auth[7:].strip())
        cand.append((self._q().get("t") or [""])[0])
        for t in cand:
            tid = resolve_tenant(t)
            if tid:
                self.tid, self.tok = tid, t
                return True
        return False

    def _deny(self, api=False):
        if api:
            return self._send(json.dumps({"error": "unauthorized"}), code=401)
        self.send_response(401)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(LOGIN.encode())))
        self.end_headers()
        self.wfile.write(LOGIN.encode())

    def do_GET(self):
        p = self.path.split("?")[0].lstrip("/")
        if not self._authed():
            return self._deny(api=p.startswith("api/"))
        if (self._q().get("t") or [""])[0]:   # token in URL -> move it into an HttpOnly cookie, drop from the bar
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", f"{COOKIE}={self.tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if p in ("", "index.html"):
            return self._send(PAGE, "text/html; charset=utf-8")
        if p == "api/state":
            return self._send(json.dumps(state(self.tid)))
        # ── Layer B surface (PRIZEHUNTER_WEB_APP_SPEC.md §1B / Phase 1). Implemented in stdlib rather than FastAPI
        # so a fresh clone needs zero dependencies; a future Next.js frontend (spec Phase 2) is then a pure client.
        if p == "api/portfolio":
            return self._send(json.dumps(api_portfolio()))
        if p == "api/fleet":
            return self._send(json.dumps(api_fleet(self.tid)))
        if p == "api/gates":
            return self._send(json.dumps(api_gates(self.tid)))
        if p.startswith("api/campaigns/"):
            return self._send(json.dumps(api_campaign(p.split("/", 2)[2])))
        if p.startswith("view/"):
            return self._send(api_view_html(p.split("/", 1)[1]), "text/html; charset=utf-8")
        self._send(json.dumps({"error": "not found"}), code=404)

    def do_POST(self):
        p = self.path.split("?")[0].lstrip("/")
        if not self._authed():
            return self._deny(api=True)
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        if p == "api/push":
            return self._send(json.dumps({"ok": True, "out": cycle(self.tid)[-2000:]}))
        if p == "api/confirm":
            try:
                key = json.loads(raw or b"{}").get("key", "")
            except Exception:
                key = ""
            if key:
                P = paths(self.tid)
                val = pendings(P).get(key, {}).get("value", "")
                with open(P["confirms"], "a") as f:   # append-only ledger; nothing is ever overwritten
                    f.write(json.dumps({"key": key, "value": val,
                                        "at": time.strftime("%FT%TZ", time.gmtime())}) + "\n")
            return self._send(json.dumps({"ok": bool(key)}))
        self._send(json.dumps({"error": "not found"}), code=404)

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--bind", default="127.0.0.1", help="0.0.0.0 to serve beyond localhost (put TLS in front)")
    ap.add_argument("--interval", type=int, default=900, help="self-push cycle seconds")
    ap.add_argument("--no-loop", action="store_true", help="serve the cockpit only (no self-push)")
    ap.add_argument("--once", action="store_true", help="run one self-push cycle per tenant and exit (cron)")
    ap.add_argument("--add-tenant", metavar="NAME", help="create a tenant; prints its token ONCE")
    ap.add_argument("--list-tenants", action="store_true")
    a = ap.parse_args()
    if a.add_tenant:
        tid, tok = add_tenant(a.add_tenant)
        print(f"  tenant '{a.add_tenant}' created (id={tid})")
        print(f"  token (shown once — store it now): {tok}")
        print(f"  login: http://127.0.0.1:{a.port}/?t={tok}")
        return
    if a.list_tenants:
        for tid, t in load_tenants().items():
            print(f"  {tid:<20} name={t.get('name')} created={t.get('created')}")
        return
    if a.once:
        for tid in load_tenants():
            print(f"== tenant {tid} ==")
            print(cycle(tid))
        return
    if not a.no_loop:
        threading.Thread(target=loop, args=(a.interval,), daemon=True).start()
        print(f"  self-push loop: every {a.interval}s")
    srv = ThreadingHTTPServer((a.bind, a.port), H)
    host = "127.0.0.1" if a.bind in ("127.0.0.1", "0.0.0.0") else a.bind
    print(f"  cockpit: http://{host}:{a.port}/?t={TOKEN}")
    print(f"  token file: {TOKENF} (0600) · tenants: {', '.join(load_tenants())}")
    if a.bind != "127.0.0.1":
        print("  ⚠ non-local bind: the token is sent in plain HTTP — terminate TLS in front (caddy/nginx/cloudflared).")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
