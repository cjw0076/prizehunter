#!/usr/bin/env bash
# gap_hunt.sh — STRUCTURAL GAP HUNTER. Two targets, one principle: keep finding the discrepancy that is
# silently eating the score (or the system), instead of polishing what is already visible.
#
# founder 2026-07-26: "train-test(public) dataset 차이 괴리, 그걸 채우기 위한 방법, 구조적 괴리를 계속 찾아낼 수
# 있도록 전략 수립" + "prizehunter 시스템 자체에도."
#
#   gap_hunt.sh comp <key> <campaign_dir> [task_type]   — hunt gaps in a COMPETITION
#   gap_hunt.sh system                                  — hunt gaps in the PRIZEHUNTER MACHINE itself
#
# Findings are not just a report: they are appended to BRIEF_BANK.md as `## COMP:<key>` directives, so the next
# drive inherits them automatically (the organic loop — a gap found today is tomorrow's instruction).
#
# Why a competition hunt matters: our biggest recorded score movements came from structural facts (a mis-set
# target, an untrusted harness, a distribution shift), not from model tuning. Why a SYSTEM hunt matters: this
# session found the machine's own worst defects by hand — a second hand-made board competing with the registry,
# drive results never recorded back so the stall/REFUTE loop could never fire, a designed recipe that was never
# enforced, targets equal to our own score. Those classes recur; hunt them on a cadence.
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; ROOT="$(cd "$CT/.." && pwd)"
BANK="${PH_BRIEF_BANK:-$CT/BRIEF_BANK.md}"
AGENT="${PH_AGENT_CMD:-codex exec --skip-git-repo-check -c model_reasoning_effort=high {PROMPT}}"
MODE="${1:-comp}"; KEY="${2:-}"; DIR="${3:-}"; TT="${4:-}"
run(){ local lg="$1"; shift; local pr="$1"; cd "$ROOT" || return 1
       # substrate CHAIN (codex→agy→claude→local): one exhausted quota must never stop the hunt
       printf '%s' "$pr" > "$R/.prompt_gap"; bash "$CT/tools/agent_run.sh" "$lg" "$R/.prompt_gap"; }

if [ "$MODE" = "comp" ]; then
  [ -z "$KEY" ] && { echo "usage: gap_hunt.sh comp <key> <campaign_dir> [task_type]"; exit 2; }
  [ -z "$DIR" ] && DIR="$(ls -d "$CT/campaigns/"*"${KEY%%-*}"* 2>/dev/null | head -1)"
  [ -z "$DIR" ] && { echo "campaign dir not found for '$KEY'"; exit 1; }
  REL="${DIR#$ROOT/}"; LG="$R/gap_${KEY}.log"
  P="You are the GAP HUNTER for competition '$KEY' (dir: $REL). Do NOT tune a model. Your job is to MEASURE the
structural discrepancies that decide the score, and to quantify each one in METRIC UNITS where possible.

Run this battery on the real data (write code, execute it, report numbers — no speculation):
1) TRAIN vs TEST(public) SHIFT — adversarial validation: train a classifier to separate train rows from test
   rows; report its AUC and the top features driving separability. AUC≈0.5 means no shift; high AUC names exactly
   which columns/segments differ. Then quantify: how much of our error sits in the shifted region?
2) CV ↔ LB CALIBRATION — collect every (local score, LB score) pair in the record. Fit the relationship: is local
   predictive (slope/offset/rank correlation)? Do fold-level gains transfer? State plainly whether our harness can
   be trusted, and if not, what harness WOULD track the LB (grouping, temporal order, row weighting).
3) PUBLIC ↔ PRIVATE STRUCTURE — from the rules/record: split sizes, split rule (random / temporal / by-group),
   and the resulting shakeup risk. Estimate how much of our public score is noise. If the final award weights
   private differently, say what that changes about what we should optimise.
4) ERROR BUDGET — decompose our error by segment (entity/time/regime/target-range). Where is the loss
   concentrated? For each segment: its share of total error, and the plausible reducible portion.
5) METRIC GEOMETRY — what does the metric reward that our loss does not (asymmetry, per-row weighting,
   ranking vs calibration, tails)? Quantify the gain available from post-hoc alignment alone.
6) LEAKAGE / DUPLICATION — near-duplicate rows across train/test, ID or ordering artefacts, target-derived
   features. Note both what we could legally exploit and what could invalidate our CV.
7) FRONTIER DELTA — given the verified #1/frontier score, allocate the gap across the findings above: which
   share of the gap does each gap explain? This is the ranked work list.

OUTPUT (both):
 a) $REL/GAP_REPORT.md — one section per probe with the numbers, then a RANKED table:
    | gap | size (metric units) | evidence | cheapest closing action |
 b) Append to $BANK a section exactly titled '## COMP:$KEY' (replace it if it already exists) holding the 3-6
    most actionable directives for the next drive, each one line, imperative, naming the number it targets.
Rules: measure, don't guess; state UNKNOWN where you could not measure and give the cheapest way to find out.
Never write 'ceiling/impossible' — an unclosable gap must still be reported with its next probe."
  echo "  🔍 gap_hunt comp [$KEY] → $REL/GAP_REPORT.md + BRIEF_BANK '## COMP:$KEY'"
  run "$LG" "$P"
  [ -f "$DIR/GAP_REPORT.md" ] && echo "  ✓ GAP_REPORT.md written ($(wc -l < "$DIR/GAP_REPORT.md") lines)" || echo "  ⚠ no GAP_REPORT.md — see $(basename "$LG")"
  grep -q "^## COMP:$KEY" "$BANK" 2>/dev/null && echo "  ✓ BRIEF_BANK now carries directives for $KEY (next drive inherits them)"
  exit 0
fi

if [ "$MODE" = "system" ]; then
  LG="$R/gap_system.log"; OUT="$CT/SYSTEM_GAP_REPORT.md"
  P="You are the GAP HUNTER aimed at the PRIZEHUNTER SYSTEM ITSELF (repo dir: competitions/control_tower). The
machine has repeatedly failed not because a mechanism was missing but because mechanisms were fragmented,
bypassed, unenforced or fed bad state. Find those defects again — mechanically, with file:line evidence.

Hunt these classes (each was a REAL defect found by hand this session, so they recur):
1) FRAGMENTATION — two sources of truth for the same fact (e.g. a hand-made board competing with
   portfolio_registry.tsv). List every duplicated state file/mechanism and say which one should win.
2) BYPASS — a designed loop that nothing feeds. Concretely: which tools write the state that goal_loop.py's
   stall_level / verdict path reads, and which drive paths skip it? Any loop whose input is never written is dead.
3) UNENFORCED DESIGN — specs in playbook/*.md (EVOLUTIONARY_RECIPE, COMPETITION_ONBOARDING, MANAGEMENT_LOOP …)
   with no code that checks compliance. For each: what a machine check would look like.
4) BAD/STALE STATE — targets equal to our own score, prose in numeric cells, statuses contradicting the record,
   registry dirs pointing at (near-)empty directories, deadlines already passed on 'live' rows.
5) DEAD CODE / ORPHANS — tools referenced by ph or docs but missing, and tools present but referenced nowhere.
6) SELF-CONSISTENCY OF THE NEW LAYER — do autopush.sh / evolve.sh / next_lever.sh / research_drive.sh /
   meta_learn.sh / brief_render.sh / open_frame.sh / audit_targets.py actually compose? Name every place where
   one expects a file or field another never produces (this class already killed drives twice).
7) WASTE — where compute/tokens go with no measurable return (drives on passed deadlines, exhausted paradigms,
   re-runs of one-shot submission work).

OUTPUT: write $OUT with a RANKED finding table:
  | severity | class | file:line | defect | fix (concrete, minimal) |
Then a short 'NEXT 3' with the highest-leverage fixes. Verify each claim by reading the actual files — no
speculation, and no praise: this document exists to find what is broken. Do not modify any tool; report only."
  echo "  🔍 gap_hunt SYSTEM → $(basename "$OUT")"
  run "$LG" "$P"
  [ -f "$OUT" ] && echo "  ✓ SYSTEM_GAP_REPORT.md written ($(wc -l < "$OUT") lines)" || echo "  ⚠ no report — see $(basename "$LG")"
  exit 0
fi
echo "usage: gap_hunt.sh comp <key> <campaign_dir> [task_type] | gap_hunt.sh system"
