#!/usr/bin/env bash
# prizehunter.sh — the one word that boots the CONTROL PLANE.
# When a user types "prizehunter" in any CLI agent, the agent runs this to see the
# whole cockpit, then assumes the Strategist persona and enters its native loop/goal
# to supervise: monitor workers, intervene on blocks, self-heal failures, reallocate.
# Read-only cockpit (refreshes board); the agent acts on what it shows.
set -u  # display cockpit: resilient, never abort mid-render
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true

# refresh the board + allocation (best-effort)
bash "$PH_HOME/tools/strategist_brief.sh" >/dev/null 2>&1 || true
bash "$PH_HOME/tools/assign_roles.sh"     >/dev/null 2>&1 || true

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  PRIZEHUNTER — CONTROL PLANE (full auto)                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo "You are now the STRATEGIST + autonomous control plane (persona: capabilities/personas/strategist.md)."
echo "The USER just watches. YOU handle everything DIRECTLY: drive workers, unblock,"
echo "self-heal the system. Surface to the human ONLY irreducible founder-gates"
echo "(external-submit auth / account ToS / explicit spend). Everything else: act."
echo
echo "── FOUNDER REQUESTS + REVIEW QUEUE (process before anything else) ─"
pending=$(grep -c "^\## \[pending\]" "$PH_HOME/founder_requests.md" 2>/dev/null || echo 0)
if [ "$pending" -gt 0 ]; then
  echo "  🚨 $pending PENDING revision request(s) — address FIRST:"
  grep "^\## \[pending\]" "$PH_HOME/founder_requests.md" | sed 's/^/  /'
else
  echo "  ✅ No pending revision requests"
fi
# Show campaigns awaiting Founder review (FEEDBACK_REQUEST.md exists but not yet parsed)
review_count=0
for fr in "$PH_HOME"/campaigns/*/FEEDBACK_REQUEST.md; do
  [ -f "$fr" ] || continue
  if grep -q "\- \[ \]" "$fr" 2>/dev/null; then
    echo "  📋 Awaiting Founder review: $(basename "$(dirname "$fr")")/FEEDBACK_REQUEST.md"
    review_count=$((review_count+1))
  fi
done
[ "$review_count" -eq 0 ] && echo "  ✅ No pending review forms"
echo
echo "── TOOL CAPABILITIES ──────────────────────────────────────────"
bash "$PH_HOME/tools/check_capabilities.sh" 2>/dev/null | grep -E "MISSING|Summary" | sed 's/^/  /' || echo "  (run: ph capabilities)"
echo "  → ph capabilities  |  ph find-tool \"<need>\"  |  marketplaces: smithery.ai · mcp.so · glama.ai/mcp"
echo
echo "── BOARD ──────────────────────────────────────────────────────"
sed -n '4,9p' "$PH_HOME/STRATEGIST_BRIEF.md" 2>/dev/null | sed 's/^/  /' || true
echo "── ROLE ASSIGNMENTS (needs · gaps · who drives what) ──────────"
sed -n '/^| competition/,/^$/p' "$PH_HOME/ROLE_ASSIGNMENTS.md" 2>/dev/null | sed 's/^/  /' || true
grep -E 'over-subscribed|OVER-SUBSCRIBED|shortfalls' "$PH_HOME/ROLE_ASSIGNMENTS.md" 2>/dev/null | sed 's/^/  ⚠ /'
echo "── WORKERS (parallel tmux campaigns) ──────────────────────────"
tmux list-windows -t "${PH_SESSION:-prizehunt}" 2>/dev/null | sed 's/^/  /' || echo "  (no worker session — launch: tools/run_parallel.sh --keys ...)"
echo
echo "── SUPERVISE LOOP (run this with your CLI's loop/goal feature) ─"
cat <<'LOOP'
  Claude:  /goal "supervise prizehunter: keep all GO campaigns moving to #1"
           or  /loop 30m  (re-run the control-plane tick on an interval)
  Codex :  set a goal; codex goals supervises the chain
  Each tick (YOU act — do not ask the user):
    1. bash tools/portfolio_tick.sh        # refresh + record + flywheel deposit
    2. drive GO campaigns autonomously:  run_campaign.sh --key <K> --execute
    3. INTERVENE DIRECTLY on blocked workers (you, not the human):
         - dispatch help:  agent_dispatch.sh --to <best agent> --task "unblock <comp>: <issue>"
         - or just fix it yourself in the worker's repo dir
         - founder gate (auth/ToS/spend)? — the ONLY thing you surface; one line, then continue others
    4. SELF-HEAL: a tool/stage errored? FIX THE SYSTEM yourself:
         record_failure_learning.sh ... → patch the tool → re-run → record the fix
    5. REALLOCATE: assign_roles.sh → move workers to highest-EV; drop dead/no-prize campaigns
    6. repeat — the user is watching a fully automatic operation
LOOP
echo "════════════════════════════════════════════════════════════════"
echo "tip: full protocol in CONTROL_PLANE.md"
