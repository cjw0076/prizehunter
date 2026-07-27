#!/usr/bin/env python3
"""dashboard_sync — portfolio_registry + status → Supabase (대시보드 데이터 동기화).
service_role로 RLS 우회 upsert. ~/.config/prizehunter/supabase.env 필요.
사용: python3 tools/dashboard_sync.py   (틱/cron에서 호출)"""
import csv, json, re, sys, urllib.request, urllib.error, pathlib, datetime

CT = pathlib.Path(__file__).resolve().parent.parent
CFG = pathlib.Path.home() / ".config/prizehunter/supabase.env"
env = {}
for ln in CFG.read_text().splitlines() if CFG.exists() else []:
    if "=" in ln: k, v = ln.split("=", 1); env[k] = v.strip()
SR = env.get("SUPABASE_SERVICE_ROLE")
REF = env.get("SUPABASE_PROJECT_REF", "jzscoykecukropmdhein")
BASE = f"https://{REF}.supabase.co/rest/v1"
if not SR:
    raise SystemExit("no service_role in supabase.env")

def now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def post(table, rows, on_conflict=None):
    url = f"{BASE}/{table}"
    if on_conflict: url += f"?on_conflict={on_conflict}"
    req = urllib.request.Request(url, data=json.dumps(rows).encode(), method="POST",
        headers={"apikey": SR, "Authorization": f"Bearer {SR}", "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status

def post_failsoft(table, rows, on_conflict=None):
    """Batch first; on failure retry per-row so one bad row cannot blank the whole board.
    Returns (ok_count, failures:[(key, http_code, body_head)])."""
    try:
        post(table, rows, on_conflict)
        return len(rows), []
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        print(f"[{now()}] {table} batch {e.code}: {body} — falling back to per-row", flush=True)
    except Exception as e:
        print(f"[{now()}] {table} batch error: {e!r} — falling back to per-row", flush=True)
    ok, failures = 0, []
    for row in rows:
        try:
            post(table, [row], on_conflict)
            ok += 1
        except urllib.error.HTTPError as e:
            failures.append((row.get("key", "?"), e.code, e.read().decode(errors="replace")[:150]))
        except Exception as e:
            failures.append((row.get("key", "?"), 0, repr(e)[:150]))
    return ok, failures

def parse_progress(cell):
    """progress column sometimes carries free text (drive workers append notes there).
    Only a standalone 0-100 integer counts as progress; anything else is 0, never a
    digit-concatenation (that produced 105-digit ints and a Postgres 400 that blanked
    the whole dashboard until 2026-07-27)."""
    m = re.match(r"\s*(\d{1,3})\s*%?\s*$", cell or "")
    if m and 0 <= int(m.group(1)) <= 100:
        return int(m.group(1))
    return 0

# competitions upsert (registry 미러)
reg = CT / "portfolio_registry.tsv"
comps = []
if reg.exists():
    rows = list(csv.reader(reg.read_text(encoding="utf-8").splitlines(), delimiter="\t"))
    for r in rows[1:]:
        if len(r) < 11: continue
        comps.append({"key": r[0], "name": r[0], "metric": r[3], "direction": r[4],
                      "best": r[5][:200], "rank1": r[6][:100], "progress": parse_progress(r[7]),
                      "status": r[8][:60], "blocker": r[9][:300], "next_lever": r[10][:400],
                      "owner_id": None})

exit_code = 0
if comps:
    ok, failures = post_failsoft("competitions", comps, on_conflict="key")
    print(f"[{now()}] competitions upsert: {ok}/{len(comps)} rows", flush=True)
    for key, code, body in failures:
        print(f"[{now()}]   FAILED row key={key} http={code} body={body}", flush=True)
    if failures: exit_code = 1

# snapshot 1건
summ = {"competitions": len(comps),
        "active": sum(1 for c in comps if "active" in c["status"].lower()),
        "submitted": sum(1 for c in comps if "submit" in c["status"].lower()),
        "blocked": sum(1 for c in comps if "block" in c["status"].lower())}
try:
    st = post("snapshots", [{"summary": summ, "source": "sync", "owner_id": None}])
    print(f"[{now()}] snapshot insert: {st}", flush=True)
except urllib.error.HTTPError as e:
    print(f"[{now()}] snapshot insert FAILED http={e.code} body={e.read().decode(errors='replace')[:200]}", flush=True)
    exit_code = 1
except Exception as e:
    print(f"[{now()}] snapshot insert FAILED: {e!r}", flush=True)
    exit_code = 1
print(f"[{now()}] synced: {summ}", flush=True)
sys.exit(exit_code)
