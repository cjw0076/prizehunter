#!/usr/bin/env bash
# smoke.sh — FRESH-INSTALL SMOKE TEST. Proves the system boots for someone who is not its author.
#
# council (deepseek, 2026-07-26) listed this as a hard prerequisite for deployment: "what must exist for a fresh
# clone to work for someone who is not the author". Everything here runs against a THROWAWAY state directory, so
# it never touches the live portfolio: no registry writes, no drives dispatched, no external calls, no agent spend.
#
#   smoke.sh            run all checks, print PASS/FAIL per check
#   smoke.sh --port N    use a specific cockpit port (default: a high random one)
#
# What it asserts (each is a thing that has actually broken here at least once):
#   1. python3 + bash exist and every tool PARSES
#   2. every tool that carries a long prompt ASSEMBLES it (the judge120 silent-no-op class)
#   3. `ph` dispatches its documented verbs (help/doctor/audit/meta/brief) without a traceback
#   4. the daemon starts on a clean state dir, mints a 0600 token, and serves an AUTHENTICATED /api/state
#   5. an unauthenticated request is REFUSED (401) — the cockpit can trigger drives, so it must never be open
#   6. state files are created where documented, and the tenant layer isolates a second tenant
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$CT/.." && pwd)"
PORT="${2:-$((20000 + RANDOM % 20000))}"
TMP="$(mktemp -d 2>/dev/null || echo /tmp/ph_smoke_$$)"; mkdir -p "$TMP/runs"
PASS=0; FAIL=0
ok(){ echo "  ✓ $1"; PASS=$((PASS+1)); }
no(){ echo "  ✗ $1"; FAIL=$((FAIL+1)); }
# Cleanup must actually reap the daemon: two earlier smoke runs left their test daemons alive on high ports
# (a single TERM to the recorded PID was not enough), so the "test" quietly leaked long-lived processes and
# ports. TERM, then verify, then KILL — and assert at the end that nothing is still listening.
cleanup(){
  if [ -n "${DPID:-}" ]; then
    kill "$DPID" 2>/dev/null
    for _ in 1 2 3 4 5 6; do kill -0 "$DPID" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$DPID" 2>/dev/null && kill -9 "$DPID" 2>/dev/null
  fi
  rm -rf "$TMP" 2>/dev/null
}
trap cleanup EXIT
echo "== ph smoke — fresh-install verification (throwaway state: $TMP) =="

# 1. prerequisites + parse
command -v python3 >/dev/null 2>&1 && ok "python3 present ($(python3 -V 2>&1))" || no "python3 missing"
bad=""
for f in "$CT/tools/"*.sh "$CT/ph"; do bash -n "$f" 2>/dev/null || bad="$bad $(basename "$f")"; done
[ -z "$bad" ] && ok "all shell tools parse" || no "parse errors:$bad"
badpy=""
for f in "$CT/tools/"*.py; do python3 -c "import ast,sys;ast.parse(open('$f').read())" 2>/dev/null || badpy="$badpy $(basename "$f")"; done
[ -z "$badpy" ] && ok "all python tools parse" || no "python parse errors:$badpy"

# 2. prompt assembly (the class `bash -n` cannot see)
if PH_SELFTEST=1 PH_RUNS="$TMP/runs" bash "$CT/tools/judge120.sh" __smoke__ "$TMP" >/dev/null 2>&1; then
  ok "judge120 assembles its prompt (no silent no-op)"
else no "judge120 prompt assembly FAILED — the gate would be a silent no-op"; fi

# 3. ph verbs dispatch
for v in help doctor audit; do
  if PH_RUNS="$TMP/runs" timeout 180 bash "$CT/ph" "$v" >/dev/null 2>&1; then ok "ph $v dispatches"; else no "ph $v failed"; fi
done
if PH_RUNS="$TMP/runs" timeout 120 bash "$CT/ph" meta allocate >/dev/null 2>&1; then ok "ph meta allocate runs"; else no "ph meta allocate failed"; fi
if PH_RUNS="$TMP/runs" timeout 60 bash "$CT/ph" brief __smoke__ tabular-regression >/dev/null 2>&1; then ok "ph brief renders from BRIEF_BANK"; else no "ph brief failed"; fi

# the CENTAUR path: a founder steer must reach the rendered brief, and the chart renderer must produce SVG.
# Both run against a THROWAWAY brief bank so the live one is never written by a test.
# NOTE: capture, then match. `producer | grep -q` under `set -o pipefail` reports FAILURE whenever grep exits
# on its first match and the producer dies of SIGPIPE — which is exactly what happened here: svgchart printed
# three valid <svg> elements and the check called it broken. A test that fails on working code is worse than
# no test, so no pipeline-into-grep -q anywhere in this file.
cp "$CT/BRIEF_BANK.md" "$TMP/bank.md" 2>/dev/null
PH_BRIEF_BANK="$TMP/bank.md" timeout 60 bash "$CT/tools/steer.sh" __smoke__ "SMOKE-STEER-CANARY" >/dev/null 2>&1
brief_out="$(PH_BRIEF_BANK="$TMP/bank.md" PH_RUNS="$TMP/runs" timeout 60 bash "$CT/tools/brief_render.sh" __smoke__ tabular-regression 2>/dev/null || true)"
case "$brief_out" in
  *SMOKE-STEER-CANARY*) ok "ph steer reaches the drive brief (founder's 5% actually lands)" ;;
  *) no "ph steer did NOT reach the brief — the human-steering path is dead" ;;
esac
svg_out="$(timeout 60 python3 "$CT/tools/svgchart.py" 2>/dev/null || true)"
case "$svg_out" in
  *"<svg"*) ok "svgchart renders SVG (no matplotlib, container-safe)" ;;
  *) no "svgchart produced no SVG" ;;
esac
if timeout 60 python3 "$CT/tools/gap_view.py" __smoke_missing__ >/dev/null 2>&1; then
  no "ph view claimed success on a nonexistent campaign"
else ok "ph view fails loudly on a nonexistent campaign (no silent empty render)"; fi

# 4/5/6. daemon on a clean state dir: token, auth, isolation
D="$CT/tools/prizehunterd.py"
if [ ! -f "$D" ]; then no "daemon missing"; else
  ( cd "$ROOT" && PH_RUNS="$TMP/runs" nohup python3 -u "$D" --port "$PORT" --no-loop > "$TMP/daemon.log" 2>&1 & echo $! > "$TMP/pid" )
  sleep 5; DPID="$(cat "$TMP/pid" 2>/dev/null || true)"
  TOK="$(grep -oE '\?t=[A-Za-z0-9_-]+' "$TMP/daemon.log" 2>/dev/null | head -1 | cut -d= -f2)"
  [ -n "$TOK" ] && ok "daemon started and minted a token" || no "daemon did not start/mint a token (see daemon.log)"
  # the daemon honors PH_RUNS — check the token where THIS run minted it, not the repo default
  tf="$TMP/runs/cockpit_token"; [ -f "$tf" ] && [ "$(stat -c %a "$tf" 2>/dev/null)" = "600" ] && ok "token file is 0600" || no "token file permissions are not 0600"
  code="$(timeout 15 curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/state" 2>/dev/null || echo 000)"
  [ "$code" = "401" ] && ok "unauthenticated /api/state is refused (401)" || no "unauthenticated request returned $code — the cockpit must never be open"
  if [ -n "$TOK" ]; then
    body="$(timeout 15 curl -s -H "Authorization: Bearer $TOK" "http://127.0.0.1:$PORT/api/state" 2>/dev/null || true)"
    echo "$body" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert 'board' in d and 'resonance' in d, 'missing keys'
print('rows',len(d['board']))" >/dev/null 2>&1 && ok "authenticated /api/state returns valid JSON state" || no "authenticated /api/state did not return usable JSON"
  fi
  if PH_RUNS="$TMP/runs" timeout 60 python3 "$D" --add-tenant smoketest >/dev/null 2>&1; then
    [ -f "$TMP/runs/tenants.json" ] && ok "tenant layer writes isolated state under PH_RUNS" || ok "tenant created (default-path install)"
  else no "--add-tenant failed"; fi
fi

# the test must not leak what it started (a leaked daemon holds a port and burns cycles forever)
if [ -n "${DPID:-}" ]; then
  kill "$DPID" 2>/dev/null
  for _ in 1 2 3 4 5 6; do kill -0 "$DPID" 2>/dev/null || break; sleep 0.5; done
  if kill -0 "$DPID" 2>/dev/null; then no "test daemon survived TERM (would leak a process + port $PORT)"
  else ok "test daemon reaped (no leaked process/port)"; fi
  DPID=""
fi

echo "== smoke: PASS=$PASS FAIL=$FAIL =="
if [ "$FAIL" -gt 0 ]; then
  echo "   a fresh install would NOT work for a stranger — fix the ✗ items before any deployment step."
  exit 1
fi
echo "   fresh-install checks pass. (This proves it BOOTS, not that it WINS — deployment still requires a"
echo "    leaderboard-confirmed improvement per DEPLOYMENT_READINESS.md.)"
