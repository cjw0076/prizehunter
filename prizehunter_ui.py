#!/usr/bin/env python3
"""prizehunter_ui — zero-dependency bridge server for the Toss-style showcase UI.

Endpoints
  GET  /                       -> prizehunter_ui.html
  GET  /api/status             -> registry rows + summary (+ per-card notes/signal counts)
  GET  /api/money              -> ROI rows from `ph money`
  GET  /api/feed               -> merged human-native notification feed
                                  (founder gates · ready-gates · agent signals)
  GET  /api/docs?key=K         -> files attached to a competition (campaign dir + ledger)
  GET  /api/file?path=REL[&dl] -> view/download a whitelisted repo file (privacy-guarded)
  POST /api/exec  {verb,key}   -> run a WHITELISTED read-only `ph` verb
  POST /api/note  {key,text}   -> attach a requirement/note to a card (ui_notes.json sidecar)

Run:  python3 prizehunter_ui.py [--port 8799]   (127.0.0.1 only)
"""
import json, os, re, subprocess, sys, glob, threading, tempfile
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

CODEX = os.environ.get("CODEX_BIN", "/home/user/bin/codex")
AGENT_JOBS = {}            # jid -> {proc, log, out, done, write, lf, prompt, started}
AGENT_LOCK = threading.Lock()

ROOT = os.path.dirname(os.path.abspath(__file__))                 # .../control_tower
REPO_ROOT = os.path.abspath(os.path.join(ROOT, "..", ".."))      # .../dacon  (registry dirs are relative to this)
REGISTRY = os.path.join(ROOT, "portfolio_registry.tsv")
HTML = os.path.join(ROOT, "prizehunter_ui.html")
PH = os.path.join(ROOT, "ph")
RECEIPTS = os.path.join(ROOT, "receipts")
OUTBOX = os.path.join(ROOT, "aios_outbox")
FREQ = os.path.join(ROOT, "founder_requests.md")
NOTES = os.path.join(ROOT, "ui_notes.json")
ROI_REPORT = os.path.join(ROOT, "ROI_REPORT.md")
_MONEY_LOCK = threading.Lock()

SAFE_VERBS = {"status", "next", "money", "gates", "submitted", "judge",
              "quality", "novelty", "doctor", "agents", "chase", "automation"}
COLS = ["key", "dir", "ledger", "metric", "direction", "best",
        "rank1", "progress", "status", "blocker", "next_lever"]
MONTHS = {m.lower(): i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}

# privacy boundary (CLAUDE.md) — never serve these
PRIVACY = ["vault", ".env", "identity", "token", "secret", "credential",
           "_from_desktop", "password", "api_key"]
# operator-private path names extend the blocklist from a gitignored local file,
# so they never appear in shipped code
_pb = os.path.expanduser("~/.config/prizehunter/privacy_blocklist.txt")
if os.path.exists(_pb):
    with open(_pb, encoding="utf-8") as _f:
        PRIVACY += [t.strip().lower() for t in _f.read().replace(",", "\n").splitlines() if t.strip()]
PRIVACY = tuple(PRIVACY)
VIEW_EXT = {".md", ".txt", ".csv", ".tsv", ".json", ".py", ".sh",
            ".html", ".htm", ".yaml", ".yml", ".log", ".cfg"}
DOC_EXT = VIEW_EXT | {".pdf", ".png", ".jpg", ".jpeg", ".ipynb", ".zip", ".mp4"}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _privacy_ok(p):
    low = p.replace("\\", "/").lower()
    return not any(tok in low for tok in PRIVACY)


def load_notes():
    if os.path.exists(NOTES):
        try:
            return json.load(open(NOTES, encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def extract_deadline(*texts):
    today = datetime.now().date()
    yr = today.year
    dates = []
    text = " ".join(t or "" for t in texts)
    # YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD (optional time)
    for m in re.finditer(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})(?:\s+\d{1,2}:\d{2})?\b", text):
        try:
            dates.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date())
        except ValueError:
            pass
    # English month + day (assume current year)
    for m in re.finditer(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})\b", text, re.I):
        try:
            dates.append(datetime(yr, MONTHS[m.group(1).lower()[:3]], int(m.group(2))).date())
        except ValueError:
            pass
    # Korean: [YYYY년] M월 D일
    for m in re.finditer(r"(?:(20\d{2})년\s*)?(\d{1,2})월\s*(\d{1,2})일", text):
        try:
            dates.append(datetime(int(m.group(1)) if m.group(1) else yr,
                                  int(m.group(2)), int(m.group(3))).date())
        except ValueError:
            pass
    # bare M/D slash (assume current year) — ponytail: heuristic, may catch a stray ratio
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})\b", text):
        mo, dy = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= dy <= 31:
            try:
                dates.append(datetime(yr, mo, dy).date())
            except ValueError:
                pass
    # D-N is relative to WRITE time, not read time — a stale "D-1" left in the
    # registry would otherwise read as "due tomorrow" forever and mask a lapsed
    # deadline. Trust D-N only when the text carries no absolute date.
    relative = []
    for m in re.finditer(r"\bD-(\d+)\b", text, re.I):
        relative.append(today + timedelta(days=int(m.group(1))))
    if not dates:
        dates = relative
    if not dates:
        return None, None
    future = [d for d in dates if d >= today]
    # all-past: report the LATEST past date (the deadline), not the earliest mention
    deadline = min(future) if future else max(dates)
    return deadline.isoformat(), (deadline - today).days


# generic tokens that match almost every receipt → useless for attribution
SIG_STOP = {"2024", "2025", "2026", "2027", "video", "media", "challenge", "dacon",
            "kaggle", "prize", "data", "contest", "design", "film", "korea", "korean",
            "seoul", "busan", "daegu", "namgu", "ledger", "autocapture", "agent", "ai"}


def signal_count(key):
    """How many agent receipts/outbox files distinctively reference this competition → 'n회차'.

    Uses only distinctive tokens (numeric contest ids, or words >=4 chars not in the
    stoplist), and excludes bare 4-digit years — otherwise '2026' matches every
    timestamped receipt and the count is meaningless.
    """
    toks = [t for t in re.split(r"[-_]", key.lower())
            if t not in SIG_STOP and len(t) >= 4 and not (t.isdigit() and len(t) == 4)]
    if not toks:
        return 0
    n = 0
    for d in (RECEIPTS, OUTBOX):
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            low = fn.lower()
            if any(t in low for t in toks):
                n += 1
    return n


def parse_registry(with_extras=True):
    rows = []
    notes = load_notes() if with_extras else {}
    if not os.path.exists(REGISTRY):
        return rows
    for line in open(REGISTRY, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts[0] == "key":
            continue
        row = {COLS[i]: (parts[i] if i < len(parts) else "") for i in range(len(COLS))}
        best, rank1 = _num(row["best"]), _num(row["rank1"])
        gap = None
        if best is not None and rank1 is not None:
            if row["direction"] == "max":
                gap = round(best - rank1, 4)
            elif row["direction"] == "min":
                gap = round(rank1 - best, 4)
        row["progress_n"] = int(_num(row["progress"]) or 0)
        row["gap"] = gap
        row["founder_gate"] = "FOUNDER" in (row["blocker"] or "").upper()
        row["deadline"], row["dday"] = extract_deadline(row["blocker"], row["next_lever"])
        if with_extras:
            row["notes"] = notes.get(row["key"], [])
            row["signals"] = signal_count(row["key"])
        rows.append(row)
    return rows


def summary(rows):
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    return {"total": len(rows), "by_status": by,
            "submitted": by.get("submitted", 0), "active": by.get("active", 0),
            "founder_gates": sum(1 for r in rows if r["founder_gate"]),
            "avg_progress": round(sum(r["progress_n"] for r in rows) / len(rows)) if rows else 0}


# ---------------- notification feed ----------------
def _ts_from_receipt(fn):
    m = re.match(r"(\d{8}T\d{6})", fn)
    if not m:
        return ""
    try:
        return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").strftime("%m/%d %H:%M")
    except ValueError:
        return ""


def _classify_receipt(slug):
    s = slug.lower()
    if "failure" in s or "blocker" in s:
        return ("warn", "⚠️", "리스크/실패 학습")
    if "tick" in s:
        return ("progress", "🔄", "자율 tick")
    if "ceiling" in s or "signal" in s:
        return ("info", "📡", "신호 갱신")
    if "asset" in s or "ledger" in s or "autocapture" in s:
        return ("done", "🗂", "자산 기록")
    if "dispatch" in s:
        return ("progress", "🤝", "에이전트 디스패치")
    return ("info", "•", "에이전트 로그")


def parse_founder_requests():
    items = []
    if not os.path.exists(FREQ):
        return items
    for line in open(FREQ, encoding="utf-8"):
        m = re.match(r"^##\s*\[([a-z_]+)\]\s*(.+?)\s*[—-]\s*([\d-]+)", line.strip())
        if m:
            status, key, date = m.group(1), m.group(2).strip(), m.group(3)
            lvl = "done" if status in ("done", "resolved", "closed") else "action"
            items.append({"level": lvl, "icon": "📌", "kind": f"founder:{status}",
                          "title": f"{key}", "detail": f"founder 요청 · {status}",
                          "key": key, "time": date})
    return items


def build_feed():
    rows = parse_registry(with_extras=False)
    feed = []
    # 1) action items from registry — 확인 필요
    for r in rows:
        if r["founder_gate"] or r["status"] == "ready-gate":
            feed.append({"level": "action", "icon": "🚦", "kind": "gate",
                         "title": r["key"], "detail": (r["blocker"] or "")[:140],
                         "key": r["key"], "time": ""})
    # 2) founder_requests.md
    feed += parse_founder_requests()
    # 3) recent agent signals (latest receipts)
    if os.path.isdir(RECEIPTS):
        files = sorted(os.listdir(RECEIPTS), reverse=True)[:18]
        for fn in files:
            slug = re.sub(r"^[0-9T+]+_", "", fn).rsplit(".", 1)[0]
            lvl, icon, label = _classify_receipt(slug)
            feed.append({"level": lvl, "icon": icon, "kind": "signal",
                         "title": slug.replace("-", " ")[:60], "detail": label,
                         "key": "", "time": _ts_from_receipt(fn)})
    counts = {}
    for f in feed:
        counts[f["level"]] = counts.get(f["level"], 0) + 1
    return {"items": feed, "counts": counts,
            "attention": counts.get("action", 0) + counts.get("warn", 0)}


# ---------------- docs / files ----------------
def list_docs(key):
    rows = {r["key"]: r for r in parse_registry(with_extras=False)}
    r = rows.get(key)
    if not r:
        return {"ok": False, "error": "unknown key"}
    out, seen = [], set()
    targets = []
    if r["dir"]:
        targets.append(os.path.join(REPO_ROOT, r["dir"]))
    for base in targets:
        if not os.path.isdir(base):
            continue
        for path in glob.glob(os.path.join(base, "**", "*"), recursive=True):
            if not os.path.isfile(path):
                continue
            rel = os.path.relpath(path, REPO_ROOT)
            if rel.count(os.sep) - r["dir"].count(os.sep) > 2:   # maxdepth 2 under dir
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext not in DOC_EXT or not _privacy_ok(rel) or rel in seen:
                continue
            seen.add(rel)
            out.append({"name": os.path.basename(path), "path": rel, "ext": ext,
                        "size": os.path.getsize(path), "viewable": ext in VIEW_EXT})
    # ledger always included if present
    if r["ledger"]:
        lp = os.path.join(REPO_ROOT, r["ledger"])
        if os.path.isfile(lp) and _privacy_ok(r["ledger"]) and r["ledger"] not in seen:
            out.insert(0, {"name": "📒 " + os.path.basename(lp), "path": r["ledger"],
                           "ext": ".md", "size": os.path.getsize(lp), "viewable": True})
    out.sort(key=lambda d: (not d["name"].startswith("📒"), d["name"].lower()))
    return {"ok": True, "key": key, "dir": r["dir"], "files": out, "notes": load_notes().get(key, [])}


def read_file(rel, dl=False):
    full = os.path.realpath(os.path.join(REPO_ROOT, rel))
    if not full.startswith(REPO_ROOT) or not os.path.isfile(full):
        return None, None
    if not _privacy_ok(os.path.relpath(full, REPO_ROOT)):
        return None, None
    ext = os.path.splitext(full)[1].lower()
    if ext not in DOC_EXT:
        return None, None
    ctype = {".md": "text/markdown", ".html": "text/html", ".htm": "text/html",
             ".csv": "text/csv", ".json": "application/json", ".pdf": "application/pdf",
             ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".mp4": "video/mp4"}.get(ext, "text/plain")
    if dl:
        ctype = "application/octet-stream"
    if os.path.getsize(full) > 4_000_000:                       # 4MB cap
        return b"(file too large to preview)", "text/plain; charset=utf-8"
    with open(full, "rb") as fh:
        return fh.read(), ctype + ("; charset=utf-8" if ctype.startswith("text") else "")


def add_note(key, text):
    text = (text or "").strip()
    if not key or not text:
        return {"ok": False, "error": "key/text required"}
    notes = load_notes()
    notes.setdefault(key, []).append(
        {"text": text[:500], "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
    json.dump(notes, open(NOTES, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "notes": notes[key]}


# ---------------- codex live agent session (UI <-> runtime CLI) ----------------
def start_agent(prompt, write=False):
    """Launch a codex runtime session.

    write=False -> read-only sandbox (queries / analysis).
    write=True  -> autonomous dev. In THIS container the bwrap workspace-write
                   sandbox is unreliable (bwrap loopback RTM_NEWADDR), so write
                   mode uses --dangerously-bypass-approvals-and-sandbox. That is
                   safe here ONLY because the whole session is already running
                   inside an external container sandbox and the server binds to
                   127.0.0.1. ponytail: bypass is the working dev path here.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt 필요"}
    if len(prompt) > 8000:
        return {"ok": False, "error": "prompt 너무 김 (8000자 제한)"}
    if not os.path.exists(CODEX):
        return {"ok": False, "error": f"codex 미설치 ({CODEX})"}
    with AGENT_LOCK:
        if any(not j["done"] for j in AGENT_JOBS.values()):
            return {"ok": False, "error": "이미 실행 중인 codex 작업이 있습니다. 완료 후 다시 시도하세요."}
        jid = f"a{len(AGENT_JOBS) + 1}"
        log = os.path.join(tempfile.gettempdir(), f"phui_{jid}.log")
        outf = os.path.join(tempfile.gettempdir(), f"phui_{jid}.out")
        base = [CODEX, "exec", "--skip-git-repo-check", "-C", REPO_ROOT, "-o", outf]
        if write:
            sandbox = "autonomous(bypass)"
            cmd = base + ["--dangerously-bypass-approvals-and-sandbox", prompt]
        else:
            sandbox = "read-only"
            cmd = base + ["-s", "read-only", prompt]
        lf = open(log, "w")
        proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=lf,
                                stderr=subprocess.STDOUT, text=True)
        AGENT_JOBS[jid] = {"proc": proc, "log": log, "out": outf, "done": False,
                           "write": write, "lf": lf, "prompt": prompt,
                           "started": datetime.now().strftime("%H:%M:%S")}
        return {"ok": True, "job": jid, "sandbox": sandbox, "started": AGENT_JOBS[jid]["started"]}


def agent_status(jid):
    j = AGENT_JOBS.get(jid)
    if not j:
        return {"ok": False, "error": "unknown job"}
    rc = j["proc"].poll()
    running = rc is None
    if not running and not j["done"]:
        j["done"] = True
        try:
            j["lf"].close()
        except Exception:
            pass
    log = ""
    try:
        log = "\n".join(l for l in open(j["log"], encoding="utf-8", errors="replace")
                        .read().splitlines() if "libtinfo" not in l)
    except Exception:
        pass
    final = ""
    if not running:
        try:
            final = open(j["out"], encoding="utf-8", errors="replace").read().strip()
        except Exception:
            pass
    return {"ok": True, "running": running, "rc": rc, "write": j["write"],
            "log": log[-7000:], "final": final, "prompt": j["prompt"][:200]}


def run_ph(verb, key=None):
    if verb not in SAFE_VERBS:
        return {"ok": False, "error": f"verb '{verb}' not allowed"}
    cmd = [PH, verb]
    if key and re.fullmatch(r"[A-Za-z0-9_\-]+", key):
        cmd.append(key)
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=40)
        txt = (out.stdout or "") + (("\n" + out.stderr) if out.stderr else "")
        txt = "\n".join(l for l in txt.splitlines() if "libtinfo" not in l)
        return {"ok": True, "verb": verb, "output": txt.strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout (40s)"}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "error": str(e)}


def _money_num(x):
    x = re.sub(r"[^\d.-]", "", x or "")
    if not x:
        return None
    try:
        n = float(x)
    except ValueError:
        return None
    return int(n) if n.is_integer() else n


def parse_money_table(text):
    rows, headers = [], []
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not headers:
            headers = [re.sub(r"\s+", " ", c).lower() for c in cells]
            continue
        if all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells):
            continue
        if len(cells) != len(headers):
            continue
        raw = dict(zip(headers, cells))
        contest = raw.get("contest", "").strip()
        if not contest:
            continue
        rows.append({
            "roi": _money_num(raw.get("roi(₩/h)") or raw.get("roi")),
            "prize": _money_num(raw.get("prize")),
            "ev": _money_num(raw.get("ev")),
            "kind": raw.get("kind", "").strip(),
            "dday": _money_num(raw.get("d-")),
            "contest": contest,
        })
    return rows


def _maybe_refresh_money(force=False):
    """Fire-and-forget: rebuild ROI_REPORT.md via `ph money` if missing/stale (>3h).

    `ph money` takes ~60s (verifies prizes), so it must NEVER block a request.
    """
    try:
        if not force and os.path.exists(ROI_REPORT):
            age = datetime.now().timestamp() - os.path.getmtime(ROI_REPORT)
            if age < 3 * 3600:
                return
        if not _MONEY_LOCK.acquire(blocking=False):
            return

        def _run():
            try:
                subprocess.run([PH, "money"], cwd=ROOT, capture_output=True, timeout=240)
            except Exception:                                    # noqa: BLE001
                pass
            finally:
                _MONEY_LOCK.release()
        threading.Thread(target=_run, daemon=True).start()
    except Exception:                                            # noqa: BLE001
        pass


def money_rows():
    """Serve the cached ROI_REPORT.md (fast); refresh it in the background if stale."""
    if not os.path.exists(ROI_REPORT):
        _maybe_refresh_money(force=True)
        return {"ok": True, "rows": [], "updated": None, "status": "building"}
    try:
        txt = open(ROI_REPORT, encoding="utf-8").read()
        updated = datetime.fromtimestamp(os.path.getmtime(ROI_REPORT)).strftime("%Y-%m-%d %H:%M")
        _maybe_refresh_money()
        rows = parse_money_table(txt)
        # display hygiene for the public showcase: drop prize_roi parse artifacts
        # (prize ≥ ₩100억 is not a real contest prize here) and dedupe by contest name,
        # keeping the highest-ROI instance. ponytail: source fix lives in prize_roi.py.
        seen, clean = set(), []
        for r in sorted(rows, key=lambda x: (x.get("roi") or 0), reverse=True):
            name = (r.get("contest") or "").strip()
            if not name or name in seen:
                continue
            if (r.get("prize") or 0) >= 1e10:
                continue
            seen.add(name)
            clean.append(r)
        return {"ok": True, "rows": clean, "updated": updated}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "error": str(e), "rows": []}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            if os.path.exists(HTML):
                self._send(200, open(HTML, "rb").read(), "text/html; charset=utf-8")
            else:
                self._send(404, b"prizehunter_ui.html missing", "text/plain")
        elif u.path == "/api/status":
            rows = parse_registry()
            self._send(200, {"summary": summary(rows), "rows": rows})
        elif u.path == "/api/money":
            self._send(200, money_rows())
        elif u.path == "/api/feed":
            self._send(200, build_feed())
        elif u.path == "/api/docs":
            self._send(200, list_docs((q.get("key") or [""])[0]))
        elif u.path == "/api/file":
            rel = (q.get("path") or [""])[0]
            data, ctype = read_file(rel, dl=bool(q.get("dl")))
            if data is None:
                self._send(404, {"error": "not found / not allowed"})
            else:
                self._send(200, data, ctype)
        elif u.path == "/api/agent/status":
            self._send(200, agent_status((q.get("id") or [""])[0]))
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"ok": False, "error": "bad json"})
        if self.path.startswith("/api/exec"):
            self._send(200, run_ph(body.get("verb", ""), body.get("key")))
        elif self.path.startswith("/api/note"):
            self._send(200, add_note(body.get("key", ""), body.get("text", "")))
        elif self.path.startswith("/api/agent"):
            self._send(200, start_agent(body.get("prompt", ""), bool(body.get("write"))))
        else:
            self._send(404, {"error": "not found"})


def main():
    port = 8799
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"prizehunter UI → http://127.0.0.1:{port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
