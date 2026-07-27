#!/usr/bin/env bash
# agent_run.sh <logfile> <prompt-file|-> — run an agent task through a SUBSTRATE FALLBACK CHAIN.
#
# founder 2026-07-26: "cli(claude head agent -> codex, claude worker(선택) -> claude, codex, agy ideation 및 분석/분해)"
# and SYSTEM_GAP_REPORT #5: a single exhausted Codex quota killed EVERY worker at once (gap hunts, drives, frames).
# One substrate = one point of total failure. This helper makes substrate a chain, not an assumption.
#
# Chain order (override with PH_AGENT_CHAIN="codex,agy,claude,local"):
#   codex  — worker of choice for focused implementation (separate quota from the head agent)
#   agy    — Google/Gemini agent CLI: ideation, analysis, decomposition, and a live fallback when codex is dry
#   claude — headless claude worker (careful: shares the head agent's quota, so it is late in the chain)
#   local  — ollama qwen3-coder:30b: free, weaker, no quota; last resort so the loop NEVER fully stops
#
# A substrate counts as FAILED (and the chain advances) when it exits non-zero, writes nothing, or its output
# matches a quota/limit/auth pattern. The winning substrate is echoed as "SUBSTRATE=<name>" on stdout so callers
# can record it (which substrate produced which gain is itself learnable).
set -uo pipefail
LOG="${1:?agent_run.sh <logfile> <prompt-file|->}"; SRC="${2:--}"
PROMPT="$([ "$SRC" = "-" ] && cat || cat "$SRC")"
# ORDER MATTERS: `claude` is LAST because it spends the head agent's own quota. Free/foreign substrates first.
CHAIN="${PH_AGENT_CHAIN:-codex,agy,local,claude}"
BACKOFF="${PH_RUNS:-$(dirname "$LOG")}/.substrate_backoff"
FAILPAT='usage limit|quota|rate.?limit|Too Many Requests|401 Unauthorized|403 Forbidden|not logged in|no credentials'

try_one(){ # try_one <name> ; returns 0 on success
  local name="$1" rc=0 before
  before="$(wc -c < "$LOG" 2>/dev/null || echo 0)"
  case "$name" in
    codex)  timeout "${PH_AGENT_TIMEOUT:-5400}" codex exec --skip-git-repo-check \
              -c model_reasoning_effort="${PH_EFFORT:-high}" "$PROMPT" >> "$LOG" 2>&1 || rc=$?;;
    agy)    timeout "${PH_AGENT_TIMEOUT:-5400}" agy --dangerously-skip-permissions -p "$PROMPT" >> "$LOG" 2>&1 || rc=$?;;
    claude) timeout "${PH_AGENT_TIMEOUT:-5400}" claude -p "$PROMPT" >> "$LOG" 2>&1 || rc=$?;;
    local)  timeout "${PH_AGENT_TIMEOUT:-5400}" ollama run "${PH_LOCAL_MODEL:-qwen3-coder:30b}" "$PROMPT" >> "$LOG" 2>&1 || rc=$?;;
    *) return 1;;
  esac
  local after grew mine
  after="$(wc -c < "$LOG" 2>/dev/null || echo 0)"; grew=$((after - before))
  # BUGFIX 2026-07-26: inspect ONLY the bytes THIS leg appended. Reading the whole log tail let an EARLIER leg's
  # "usage limit" text condemn a LATER leg that had actually succeeded — that false negative walked the chain all
  # the way to the `claude` leg and burned the head agent's own quota. Cross-leg contamination, now impossible.
  mine="$(tail -c "+$((before + 1))" "$LOG" 2>/dev/null || true)"
  if [ "$rc" -ne 0 ] && [ "$grew" -lt 200 ]; then echo "  ⤫ $name failed (rc=$rc, ${grew}B)" >&2; return 1; fi
  if [ "$grew" -lt 200 ]; then echo "  ⤫ $name produced nothing (${grew}B)" >&2; return 1; fi
  if printf '%s' "$mine" | grep -qiE "$FAILPAT"; then echo "  ⤫ $name hit a quota/auth wall (its own output)" >&2; return 1; fi
  # a substantive answer with a non-zero exit code is still an answer (agy exits non-zero routinely)
  return 0
}

IFS=',' read -r -a subs <<< "$CHAIN"
for s in "${subs[@]}"; do
  s="$(printf '%s' "$s" | tr -d ' ')"; [ -z "$s" ] && continue
  command -v "${s%%:*}" >/dev/null 2>&1 || { [ "$s" = local ] && ! command -v ollama >/dev/null && continue; }
  # BACKOFF: a substrate that just failed (concurrency/quota) is skipped for a cooling period instead of being
  # retried by every parallel drive — that stampede is what pushed the chain down to the `claude` leg.
  if [ -f "$BACKOFF.$s" ]; then
    age="$(python3 -c "
import os,time
try: print(int(time.time()-os.path.getmtime('$BACKOFF.$s')))
except Exception: print(99999)" 2>/dev/null)"
    if [ "${age:-99999}" -lt "${PH_BACKOFF_SEC:-900}" ]; then echo "  ⤫ $s skipped (cooling ${age}s < ${PH_BACKOFF_SEC:-900}s)" >&2; continue; fi
    rm -f "$BACKOFF.$s"
  fi
  echo "  → substrate: $s" >&2
  printf '\n===== substrate: %s =====\n' "$s" >> "$LOG"
  if try_one "$s"; then echo "SUBSTRATE=$s"; exit 0; fi
  : > "$BACKOFF.$s" 2>/dev/null || true       # mark this substrate cooling so parallel drives stop stampeding it
done
echo "SUBSTRATE=none" ; echo "  ⛔ every substrate in the chain failed ($CHAIN) — this is a real blocker, record it" >&2
exit 1
