#!/usr/bin/env bash
# next_lever.sh <board_key> [campaign_dir] [task_type] — the SELF-DRIVING next-lever launcher.
#
# This is what makes the daemon push WITHOUT a human in the loop: it assembles a rich brief from
#   (a) the competition's own WORKLOG/RECON (what has been tried, the LB-calibrated harness),
#   (b) the current best/target/direction from the autopush board,
#   (c) **the COMPOUNDING lever library primed by task_type** (proven levers + known dead-ends from OTHER
#       competitions) — so every drive starts smarter than the last one,
# and hands it to the user's agent CLI. The worker must write its honest best score to
# .runs/drive_<key>.score, which autopush harvests (improvement -> confirm queue).
#
# Agent CLI is configurable so this is general, not tied to one vendor:
#   PH_AGENT_CMD='codex exec --skip-git-repo-check -c model_reasoning_effort=high {PROMPT}'   (default)
#   e.g. 'claude -p {PROMPT}' · 'gemini -p {PROMPT}' · 'ollama run qwen3-coder:30b {PROMPT}'
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="$CT/.runs"; ROOT="$(cd "$CT/.." && pwd)"
KEY="${1:?board_key}"; DIR="${2:-}"; TT="${3:-}"
# TARGET LOOKUP — the REGISTRY is the single source of truth (direction/best/rank1); the legacy board is only
# a fallback. This kills the fragmentation where a drive could not find its own numbers and died instantly.
lookup_target(){ python3 - "$1" "$CT/portfolio_registry.tsv" "${PH_BOARD:-$R/autopush_board.tsv}" <<'PYEOF'
import sys
key, reg, board = sys.argv[1], sys.argv[2], sys.argv[3]
cols=[]
try:
    for l in open(reg):
        if l.startswith("#   ") and l[4:5].isalpha() and len(l.split()) > 1: cols.append(l.split()[1])
        elif not l.startswith("#"): break
    for l in open(reg):
        if l.startswith(key+"\t"):
            f=l.rstrip("\n").split("\t"); g=lambda n: f[cols.index(n)] if n in cols and cols.index(n)<len(f) else ""
            print("\t".join([g("direction") or "max", g("best") or "-", g("rank1") or "-"])); sys.exit()
except Exception: pass
try:
    for l in open(board):
        if l.startswith(key+"\t"):
            f=l.rstrip("\n").split("\t")
            print("\t".join([f[2] if len(f)>2 else "max", f[3] if len(f)>3 else "-", f[4] if len(f)>4 else "-"])); sys.exit()
except Exception: pass
print("max\t-\t-")
PYEOF
}
tgt="$(lookup_target "$KEY")"
dir="$(printf '%s' "$tgt" | cut -f1)"; best="$(printf '%s' "$tgt" | cut -f2)"; target="$(printf '%s' "$tgt" | cut -f3)"
[ "$best" = "-" ] && [ "$target" = "-" ] && { echo "no target info for '$KEY' in registry or board"; exit 1; }
[ -z "$DIR" ] && DIR="$(ls -d "$CT/campaigns/"*"${KEY%%-*}"* 2>/dev/null | head -1)"
[ -z "$DIR" ] && { echo "campaign dir not found for '$KEY' (pass it as \$2)"; exit 1; }
REL="${DIR#$ROOT/}"
better="lower"; [ "$dir" = "max" ] && better="higher"

# what the system has already learned for this task-type (positive levers AND dead-ends)
PRIME="$(bash "$CT/tools/learn.sh" prime "${TT:-$KEY}" 2>/dev/null | sed 's/^/    /')"
# what this competition itself has recorded
CTX="$(head -c 3000 "$DIR/WORKLOG.md" 2>/dev/null || head -c 3000 "$DIR/RECON.md" 2>/dev/null)"

# the brief is COMPOSED from the mutable prompt layer (BRIEF_BANK.md): GLOBAL + VARIANT + COMP + learned levers
# + measured gaps + tagged priors. The head agent edits that file; drives pick it up with no code change.
BRIEF="$(PH_CAMP_DIR="$DIR" bash "$CT/tools/brief_render.sh" "$KEY" "${TT:-}" 2>"$R/.var_$KEY")"
VARIANT="$(grep -oE 'VARIANT=[A-Za-z0-9_-]+' "$R/.var_$KEY" 2>/dev/null | head -1 | cut -d= -f2)"; VARIANT="${VARIANT:-default}"
PROMPT="REAL leaderboard drive for '$KEY'. Metric direction: $better is better. Current validated best: $best. Target: $target.
Working dir: $REL (read its WORKLOG.md / RECON.md FIRST — it holds the LB-calibrated local validation harness).

$BRIEF

=== THIS COMPETITION'S OWN RECORD (head) ===
$CTX

TASK: find and validate the NEXT lever that beats $best on the competition's own LB-calibrated local CV harness (same folds/rows/metric — never invent a new comparator). Rules:
- Only keep a change that STRICTLY beats $best on that harness; revert anything that regresses.
- Report per-fold numbers, not just the pooled score. Guard against a single fold blowing up.
- no-launder: if nothing beats $best, say so plainly — an honest negative is a valid result and gets recorded as a dead-end for future drives.
- Beware validation artifacts (row-density/checkpoint-count sensitivity, leakage via target-derived features, non-nested hyperparameter selection). Validate on the authoritative grid.
- Update the submission artifact ONLY on a strict win.
- Do NOT submit externally (no Kaggle/CrunchDAO/DACON upload) — that is a separate confirmed step.
FINALLY: write ONLY the bare best score number (e.g. 8.6231) to '$R/drive_$KEY.score' so the autopush harvester can read it. Then summarise: new score, what changed, per-fold, and one sentence on the next lever to try."

CMD="${PH_AGENT_CMD:-codex exec --skip-git-repo-check -c model_reasoning_effort=high {PROMPT}}"
LOG="$R/drive_${KEY}.log"
cd "$ROOT" || exit 1
if [ "${PH_DRY:-0}" = "1" ]; then echo "== DRY: prompt for $KEY (${#PROMPT} chars) =="; echo "$PROMPT" | head -30; exit 0; fi
# Runs the agent in the FOREGROUND on purpose: the caller (autopush / a shell) backgrounds this script and
# registers ITS pid, so one process owns the drive's lifetime — no double registration, no orphan PIDs.
echo "  🚀 $KEY: next-lever drive starting (best $best → $target, brief variant='$VARIANT')"
# shellcheck disable=SC2086
printf '%s' "$PROMPT" > "$R/.prompt_$KEY"
SUB="$(bash "$CT/tools/agent_run.sh" "$LOG" "$R/.prompt_$KEY" | grep -oE 'SUBSTRATE=[a-z]+' | cut -d= -f2)"
echo "  substrate used: ${SUB:-none}"
# SCALE DECLARATION (doctor: SCALE MIXING). A drive has no leaderboard access, so any number it writes is a
# LOCAL validation score. Declaring it keeps the harvester from recording a local gain as leaderboard progress
# — the failure that makes a local 0.95367 look like it passed playground-s6e7's rank1 0.95306.
[ -s "$R/drive_${KEY}.score" ] && printf 'local\n' > "$R/drive_${KEY}.scale"
