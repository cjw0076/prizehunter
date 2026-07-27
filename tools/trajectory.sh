#!/usr/bin/env bash
# trajectory.sh — agents log heartbeats here so the control tower can track whether
# they're making progress, spinning, blocked, or giving up. Two modes:
#   log <comp> <status> <detail>   append one heartbeat
#     status: progress | done | blocked | giveup | gated | closed | scoring
#       blocked/giveup = a wall I CAN clear (browser/data/tool) => dashboard says "intervene"
#       gated = founder-only (account signup / external submit / spend) => NOT my wall, no ping
#       closed = competition dead/deadline-passed => archived, not enterable, no ping
#       scoring = submitted, remote eval in progress => no local compute expected, no ping (not a stall)
#   watch                          control-tower dashboard: flags only ACTIONABLE stalls/blocks
# Heartbeats: .runs/trajectory/<comp>.jsonl  (ts, status, detail). No secrets in detail.
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"
DIR="$CT/.runs/trajectory"; mkdir -p "$DIR"
STALL_MIN="${PH_STALL_MIN:-20}"   # no progress heartbeat in N min => stalled/spinning

now() { date -u +%s; }
iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }

case "${1:-watch}" in
  log)
    comp="${2:?comp}"; status="${3:?status}"; shift 3; detail="$*"
    f="$DIR/$(echo "$comp" | tr -c 'a-zA-Z0-9_-' '_').jsonl"
    printf '{"ts":%s,"iso":"%s","status":"%s","detail":%s}\n' \
      "$(now)" "$(iso)" "$status" "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$detail" 2>/dev/null || echo '""')" >> "$f"
    ;;
  watch)
    t=$(now); any=0
    printf '== Control-tower trajectory (stall=%smin) ==\n' "$STALL_MIN"
    for f in "$DIR"/*.jsonl; do
      [ -e "$f" ] || continue
      any=1; comp="$(basename "$f" .jsonl)"
      last="$(tail -1 "$f")"
      lts=$(echo "$last" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read()).get("ts",0))' 2>/dev/null || echo 0)
      lstatus=$(echo "$last" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read()).get("status",""))' 2>/dev/null || echo "?")
      ldetail=$(echo "$last" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read()).get("detail","")[:70])' 2>/dev/null || echo "")
      age=$(( (t - lts) / 60 ))
      n=$(wc -l < "$f")
      flag="ok"
      case "$lstatus" in
        blocked) flag="🚧 BLOCKED — intervene (wall I can clear)" ;;
        giveup)  flag="🛑 GAVE UP — intervene" ;;
        gated)   flag="🔒 founder-gate — awaiting founder (NOT my wall)" ;;
        closed)  flag="🗄 closed — archived, not enterable" ;;
        scoring) flag="⏳ scoring — submitted, remote eval in progress (no local compute expected)" ;;
        done)    flag="✅ done" ;;
        *) if [ "$age" -ge "$STALL_MIN" ]; then
             # distinguish a real stall from a long legit compute: is heavy python running?
             busy=$(ps -eo pcpu,comm 2>/dev/null | awk '$2=="python" && $1>60' | head -1)
             if [ -n "$busy" ]; then
               flag="⚙️ long-compute ${age}min (heavy python active — likely working, not stalled)"
             else
               flag="🌀 STALLED ${age}min, NO active compute (spinning/dead?) — check"
             fi
           fi ;;
      esac
      printf '  %-28s [%s] %dmin ago · %d steps · %s\n     └ %s\n' "$comp" "$lstatus" "$age" "$n" "$flag" "$ldetail"
    done
    [ "$any" = 0 ] && echo "  (no active agent trajectories)"
    echo "→ intervene ONLY on 🚧BLOCKED/🛑GAVEUP/🌀STALLED (walls I can clear). 🔒gated=founder, 🗄closed=archive, ✅done=leave."
    ;;
esac
