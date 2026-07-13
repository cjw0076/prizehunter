#!/usr/bin/env bash
# run_parallel.sh — open one tmux window per competition so CLI agents drive many
# campaigns in PARALLEL (not one at a time). Agent-agnostic: each window launches
# the routed/selected CLI agent primed to drive that campaign, or runs the
# headless autonomous loop with --execute.
#
# Usage:
#   run_parallel.sh                         # all active GO comps from registry, interactive
#   run_parallel.sh --keys 236716,moct_ai_data --agent codex
#   run_parallel.sh --keys K1,K2 --execute  # headless run_campaign loop per window
#   run_parallel.sh --attach                # attach to the session after creating
set -euo pipefail
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"; . "$PH_HOME/config.sh"
REG="$PH_HOME/portfolio_registry.tsv"
SESSION="${PH_SESSION:-prizehunter}"; AGENT="claude"; KEYS=""; EXECUTE=0; ATTACH=0
while [ "$#" -gt 0 ]; do case "$1" in
  --keys) KEYS="$2"; shift 2;; --agent) AGENT="$2"; shift 2;;
  --execute) EXECUTE=1; shift;; --attach) ATTACH=1; shift;;
  --session) SESSION="$2"; shift 2;; *) echo "unknown: $1" >&2; exit 2;; esac; done
command -v tmux >/dev/null || { echo "tmux not installed" >&2; exit 2; }

# default: active, non-FOUNDER-blocked competitions from the registry
if [ -z "$KEYS" ]; then
  KEYS="$(awk -F'\t' 'NR>1 && $1!~"^#" && $1!="key" && $9!="blocked"{print $1}' "$REG" | paste -sd, -)"
fi
[ -n "$KEYS" ] || { echo "no competitions to run (add rows to portfolio_registry.tsv)" >&2; exit 2; }

# ensure each has a campaign plan (+ recalled expertise)
IFS=',' read -ra K <<< "$KEYS"
for k in "${K[@]}"; do
  [ -f "$PH_HOME/campaigns/$k/PLAN.json" ] || {
    name="$(awk -F'\t' -v a="$k" '$1==a{print $2}' "$REG")"; name="${name:-$k}"
    python3 "$PH_HOME/tools/plan_campaign.py" --key "$k" --name "$name" >/dev/null 2>&1 || true; }
done

tmux has-session -t "$SESSION" 2>/dev/null && { echo "session '$SESSION' exists; kill it or use --session NAME"; exit 1; }

first=1
for k in "${K[@]}"; do
  k="$(echo "$k" | tr -d ' ')"; [ -z "$k" ] && continue
  if [ "$EXECUTE" -eq 1 ]; then
    cmd="cd $PH_REPO && bash $PH_HOME/tools/run_campaign.sh --key $k --execute; exec bash"
  else
    disp="$(awk -F'\t' -v a="$AGENT" '$1==a{print $5}' "$PH_HOME/capabilities/_registry.tsv")"
    prime="You are driving competition campaign '$k'. Read $PH_REPO/CLAUDE.md, campaigns/$k/PLAN.md, and campaigns/$k/EXPERTISE.md (accumulated MemoryOS expertise). Drive it toward #1; update portfolio_registry.tsv; record. Use agent_dispatch.sh to hand off when blocked."
    # launch the agent interactively with the priming prompt as initial arg
    launch="${disp/\{TASK\}/$(printf '%q' "$prime")}"
    cmd="cd $PH_REPO && echo '== campaign $k ==' && echo $(printf '%q' "$prime") && ${launch%% -p*} ; exec bash"
    # for interactive agents, just cd + show the brief + drop into a shell ready to launch
    cmd="cd $PH_REPO && printf '== PRIZEHUNTER campaign: %s ==\n%s\n\nlaunch: %s\n' '$k' $(printf '%q' "$prime") '$disp'; exec bash"
  fi
  if [ "$first" -eq 1 ]; then tmux new-session -d -s "$SESSION" -n "$k" "$cmd"; first=0
  else tmux new-window -t "$SESSION" -n "$k" "$cmd"; fi
done

n=$(tmux list-windows -t "$SESSION" 2>/dev/null | wc -l)
echo "opened tmux session '$SESSION' with $n parallel campaign window(s): $KEYS"
echo "mode: $([ $EXECUTE -eq 1 ] && echo 'headless run_campaign --execute' || echo "interactive ($AGENT prime)")"
echo "attach: tmux attach -t $SESSION   |   list: tmux list-windows -t $SESSION"
[ "$ATTACH" -eq 1 ] && exec tmux attach -t "$SESSION"
