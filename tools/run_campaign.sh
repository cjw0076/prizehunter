#!/usr/bin/env bash
# run_campaign.sh — the one-touch executor. Walks campaigns/<key>/PLAN.json and
# drives each sub-objective + deliverable toward done, dispatching to the routed
# agent via agent_dispatch.sh, recording each step to AIOS, looping until the
# plan is complete or a step blocks (named stop condition).
#
# DEFAULT IS --dry-run (prints the dispatch plan). Real agent execution (--execute)
# spawns cost and is an autonomy step — keep external submission founder-gated.
#
# Usage: run_campaign.sh --key 236716 [--execute] [--phase phase1_qualifier]
set -euo pipefail
CONTROL="$(cd -- "$(dirname "$0")/.." && pwd)"
ROOT="$(cd -- "$CONTROL/../.." && pwd)"
REG="$CONTROL/portfolio_registry.tsv"
KEY=""; EXECUTE=0; ONLY_PHASE=""
while [ "$#" -gt 0 ]; do case "$1" in
  --key) KEY="$2"; shift 2;; --execute) EXECUTE=1; shift;;
  --phase) ONLY_PHASE="$2"; shift 2;; -h|--help) sed -n '2,12p' "$0"; exit 0;;
  *) echo "unknown: $1" >&2; exit 2;; esac; done
[ -n "$KEY" ] || { echo "need --key" >&2; exit 2; }
CAMP_DIR_REL="$(awk -F'\t' -v k="$KEY" 'BEGIN{seen=0} /^#/||NF==0{next} !seen{seen=1; next} $1==k{print $2; exit}' "$REG" 2>/dev/null || true)"
if [ -n "$CAMP_DIR_REL" ]; then
  CAMP="$ROOT/$CAMP_DIR_REL"
else
  CAMP="$CONTROL/campaigns/$KEY"
fi
PLAN="$CAMP/PLAN.json"
[ -f "$PLAN" ] || { echo "no plan: $PLAN (run plan_campaign.py first)" >&2; exit 2; }

NAME="$(python3 -c "import json;print(json.load(open('$PLAN'))['name'])")"
DOM="$(python3 -c "import json;d=json.load(open('$PLAN'));print(d.get('domain',''),d.get('metric',''))")"
mode=$([ "$EXECUTE" -eq 1 ] && echo EXECUTE || echo DRY-RUN)
echo "== run_campaign [$mode] : $NAME =="

# RECALL accumulated expertise from MemoryOS -> the agent starts as an expert (flywheel).
EXP="$CAMP/EXPERTISE.md"
"$CONTROL/tools/memoryos_bridge.sh" recall --task "$NAME $DOM competition leaderboard honest CV" >"$EXP" 2>/dev/null \
  && echo "  expertise recalled -> $EXP ($(grep -c '^- ' "$EXP" 2>/dev/null || echo 0) items)" \
  || echo "  (MemoryOS recall unavailable; proceeding without priming)"

# emit (phase, subobj_id, route, task) tuples, optionally filtered to one phase
python3 - "$PLAN" "$ONLY_PHASE" <<'PY' | while IFS=$'\t' read -r phase sid route task; do
import json,sys
plan=json.load(open(sys.argv[1])); only=sys.argv[2]
for ph in plan["phases"]:
    if only and ph["id"]!=only: continue
    for s in ph["sub_objectives"]:
        if s.get("status")=="done": continue
        print(f"{ph['id']}\t{s['id']}\t{s['route']}\t{s['task']}")
PY
  fulltask="[$NAME / $phase / $sid] $task. Read AGENTS.md/CLAUDE.md + $EXP (accumulated MemoryOS expertise — you are an expert) first; use mined corpus + methodology; update portfolio_registry + record."
  if [ "$EXECUTE" -eq 1 ]; then
    AGENT=campaign "$CONTROL/tools/agent_dispatch.sh" --to "$route" --task "$fulltask" --escalate claude,gemini </dev/null >/dev/null 2>&1 \
      && echo "  ✅ $phase/$sid via $route" || { echo "  ⛔ $phase/$sid BLOCKED via $route — stopping (named stop condition)"; exit 3; }
  else
    echo "  → dispatch $phase/$sid to $route"
    AGENT=campaign "$CONTROL/tools/agent_dispatch.sh" --to "$route" --task "$fulltask" --dry-run </dev/null 2>&1 | grep -m1 dry-run | sed 's/^/     /'
  fi
done

echo ""
echo "== deliverables =="
python3 - "$PLAN" <<'PY'
import json,sys
for d in json.load(open(sys.argv[1]))["deliverables"]:
    tag="🤖auto -> tools/make_presentation_kit.py / build agents" if d["auto"] else "🙋human-gated (prepare artifact, human finishes)"
    print(f"  [{d['status']}] {d['id']}: {tag}")
PY
echo ""
[ "$EXECUTE" -eq 1 ] && echo "executed; see capabilities/dispatch_log/ + receipts/" || \
  echo "dry-run only. add --execute to dispatch for real (cost; external submission stays founder-gated)."
