#!/usr/bin/env bash
# agent_dispatch.sh — universal cross-agent dispatch bus.
# ANY CLI agent (claude/codex/gemini/qwen/kimi/local) can call this to hand work
# to ANY OTHER agent, with capability-aware routing, blocked->escalate fallback,
# and automatic AIOS recording. Orchestrator-agnostic: it's plain shell, so
# whichever agent a user runs as "main" can drive it.
#
# Usage:
#   agent_dispatch.sh --to gemini --task "brainstorm 3 attacks on this ceiling"
#   agent_dispatch.sh --to codex  --task "implement X" --from claude --escalate gemini,claude
#   agent_dispatch.sh route --need "heavy implementation"     # recommend an agent
#   agent_dispatch.sh list                                    # show installed agents
#
# Flags: --to AGENT  --task TEXT  [--from AGENT] [--timeout SEC]
#        [--escalate a,b,c]  [--model M (local)]  [--dry-run]
set -euo pipefail

CONTROL="$(cd -- "$(dirname "$0")/.." && pwd)"
CAP="$CONTROL/capabilities"
REG="$CAP/_registry.tsv"
LOGDIR="$CAP/dispatch_log"; mkdir -p "$LOGDIR"
FROM="${AGENT:-unknown}"; TO=""; TASK=""; TIMEOUT=600; ESC=""; MODEL=""; DRY=0

reg_field() { # $1=agent $2=colindex(1-based) -> value
  awk -F'\t' -v a="$1" -v c="$2" '$1==a{print $c; exit}' "$REG"
}
installed_agents() { awk -F'\t' 'NR>1 && $1!~"^#" && $4=="yes"{print $1}' "$REG"; }

cmd="${1:-}"
case "$cmd" in
  add)
    # register ANY cli agent in one line:
    #   agent_dispatch.sh add grok --dispatch 'grok -p {TASK}' [--vendor xai --model grok --tier mid --route-to "..." --route-away "..."]
    shift; name="${1:?need agent name}"; shift
    d_vendor="?"; d_model="?"; d_disp=""; d_tier="mid"; d_to="general"; d_away="-"
    while [ "$#" -gt 0 ]; do case "$1" in
      --dispatch) d_disp="$2"; shift 2;; --vendor) d_vendor="$2"; shift 2;;
      --model) d_model="$2"; shift 2;; --tier) d_tier="$2"; shift 2;;
      --route-to) d_to="$2"; shift 2;; --route-away) d_away="$2"; shift 2;;
      *) shift;; esac; done
    [ -n "$d_disp" ] || { echo "need --dispatch 'cli ... {TASK}'" >&2; exit 2; }
    if awk -F'\t' -v a="$name" 'NR>1 && $1==a{f=1} END{exit !f}' "$REG"; then
      echo "agent '$name' already registered; edit $REG to change it" >&2; exit 1; fi
    bin="$(printf '%s' "$d_disp" | awk '{print $1}')"
    inst="$(command -v "$bin" >/dev/null 2>&1 && echo yes || echo no)"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$d_vendor" "$d_model" "$inst" "$d_disp" "$d_tier" "$d_to" "$d_away" >> "$REG"
    echo "added '$name' (installed=$inst). dispatch: $d_disp"
    exit 0;;
  list)
    printf 'agent      installed  tier  route_to\n'
    awk -F'\t' 'NR>1 && $1!~"^#" && $1!="agent"{printf "%-10s %-9s %-5s %s\n",$1,$4,$6,$7}' "$REG"; exit 0;;
  route)
    shift; need=""; [ "${1:-}" = "--need" ] && need="$2"
    printf 'recommendation for: %s\n' "$need"
    awk -F'\t' -v n="$need" 'NR>1 && $1!~"^#" && $4=="yes" {
      score=0; nlow=tolower(n); rt=tolower($7);
      split(nlow,w," "); for(i in w) if(index(rt,w[i])) score++;
      printf "%d\t%s\t%s\n",score,$1,$7 }' "$REG" | sort -rn | head -3 \
      | awk -F'\t' '{printf "  [%s] %s — %s\n",$1,$2,$3}'
    exit 0;;
esac

while [ "$#" -gt 0 ]; do
  case "$1" in
    --to) TO="$2"; shift 2;; --task) TASK="$2"; shift 2;;
    --from) FROM="$2"; shift 2;; --timeout) TIMEOUT="$2"; shift 2;;
    --escalate) ESC="$2"; shift 2;; --model) MODEL="$2"; shift 2;;
    --dry-run) DRY=1; shift;; -h|--help) sed -n '2,20p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
[ -n "$TO" ] && [ -n "$TASK" ] || { echo "need --to and --task" >&2; exit 2; }

run_agent() { # $1=agent -> echoes output, returns rc
  local agent="$1" tmpl bin
  tmpl="$(reg_field "$agent" 5)"
  if [ -z "$tmpl" ]; then echo "[dispatch] unknown agent: $agent" >&2; return 3; fi
  bin="$(printf '%s' "$tmpl" | awk '{print $1}')"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "[dispatch] $agent CLI ($bin) not installed" >&2; return 4
  fi
  # build command from template ({TASK}/{MODEL} substitution)
  local cmdline="${tmpl/\{TASK\}/$(printf '%q' "$TASK")}"
  cmdline="${cmdline/\{MODEL\}/${MODEL:-llama3}}"
  if [ "$DRY" -eq 1 ]; then echo "[dry-run] $cmdline"; return 0; fi
  timeout "$TIMEOUT" bash -c "$cmdline" 2>&1
}

stamp="$(date '+%Y%m%dT%H%M%S%z')"
log="$LOGDIR/${stamp}_${FROM}-to-${TO}.md"
attempts="$TO"; [ -n "$ESC" ] && attempts="$TO,$ESC"

out=""; used=""; rc=1
IFS=',' read -ra chain <<< "$attempts"
for a in "${chain[@]}"; do
  a="$(echo "$a" | tr -d ' ')"; [ -z "$a" ] && continue
  echo "[dispatch] $FROM -> $a ..." >&2
  if out="$(run_agent "$a")"; then used="$a"; rc=0; break
  else echo "[dispatch] $a failed/blocked (rc=$?), escalating..." >&2; fi
done

{
  echo "# Dispatch: $FROM -> $used"
  echo "- when: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "- chain tried: $attempts"
  echo "- rc: $rc"
  echo ""; echo "## Task"; echo "$TASK"
  echo ""; echo "## Output"; echo '```'; echo "$out" | head -200; echo '```'
} > "$log"

# record to AIOS (best-effort; non-fatal)
if [ "$DRY" -eq 0 ] && command -v "$CONTROL/tools/record_asset_receipt.sh" >/dev/null 2>&1; then
  "$CONTROL/tools/record_asset_receipt.sh" --contest control_tower \
    --asset "dispatch-${FROM}-to-${used:-none}-${stamp}" --type decision \
    --status "$([ $rc -eq 0 ] && echo done || echo blocked)" \
    --summary "Cross-agent dispatch: $FROM -> ${used:-none} (chain: $attempts). Task: ${TASK:0:160}" \
    --evidence "capabilities/dispatch_log/$(basename "$log")" \
    --next "consumer reads dispatch output" >/dev/null 2>&1 || true
fi

echo "$out"
echo "[dispatch] done via=${used:-none} rc=$rc log=${log#$CONTROL/}" >&2
exit $rc
