#!/usr/bin/env bash
# kernel_submit.sh — autonomous submit path for KERNELS-ONLY Kaggle competitions.
# Wraps a self-contained script as a Kaggle kernel, pushes+runs it (offline, reads
# /kaggle/input/<comp>/), and reports status. The kernel writes
# /kaggle/working/submission.csv, which is then submitted to the competition.
#
# usage: kernel_submit.sh --dir <kernel_dir> --comp <slug> --slug <kernel-slug> \
#                         [--title "T"] [--gpu] [--accelerator ACC] [--push-only]
# The kernel_dir must contain the code file (default kernel.py or first *.py).
# Requires: kaggle CLI authenticated; KAGGLE username auto-read from ~/.kaggle.
#
# HARD-WON GOTCHAS (openai ai-agent-security, 2026-07-20 — save yourself the loop):
#  - ACCELERATOR: some comps BAN P100 and require GPU T4x2. `--gpu` alone → P100 → hard
#    reject. Pass `--accelerator NvidiaTeslaT4` — it writes `machine_shape` into the
#    metadata. **Exact case matters**: lowercase `nvidiaTeslaT4` is silently ignored and
#    falls back to P100. Valid values incl. NvidiaTeslaT4, NvidiaTeslaP100, none.
#  - SERVE-BASED / OUTPUT-FILE comps (kaggle_evaluation inference-server): the visible
#    "Save & Run All" writes NO submission.csv, but submit-validation demands one. Fix in
#    the KERNEL: write a placeholder submission.csv (the few required rows) on the visible
#    run, and call the framework's serve() for the scored rerun. Real score comes from the
#    rerun, not the placeholder.
#  - SLOTS: a REJECTED submission (validation fail) does NOT consume a daily slot — iterate
#    the plumbing freely; only ACCEPTED submissions count against N/day.
#  - SUBMIT PATH for code comps: Kaggle MCP `create_code_competition_submission`
#    (kernelVersion + fileName="submission.csv") is more reliable than `competitions submit -k`.
set -uo pipefail
KAGGLE="$HOME/miniconda3/bin/kaggle"
PY="$HOME/miniconda3/bin/python"

DIR=""; COMP=""; SLUG=""; TITLE=""; GPU="false"; ACC=""; PUSH_ONLY=0
while [ $# -gt 0 ]; do case "$1" in
  --dir) DIR="$2"; shift 2;; --comp) COMP="$2"; shift 2;; --slug) SLUG="$2"; shift 2;;
  --title) TITLE="$2"; shift 2;; --gpu) GPU="true"; shift;;
  --accelerator) ACC="$2"; GPU="true"; shift 2;; --push-only) PUSH_ONLY=1; shift;;
  *) shift;; esac; done
[ -n "$DIR" ] && [ -n "$COMP" ] && [ -n "$SLUG" ] || { echo "usage: kernel_submit.sh --dir D --comp SLUG --slug KSLUG [--title T] [--gpu] [--push-only]"; exit 2; }
USER="$($PY -c "import json,os;print(json.load(open(os.path.expanduser('~/.kaggle/kaggle.json')))['username'])" 2>/dev/null)"
[ -n "$USER" ] || USER="$($KAGGLE config view 2>/dev/null | tr -d '\r' | sed -n 's/^- username: //p' | head -1)"
[ -n "$USER" ] || { echo "no kaggle username (tried kaggle.json + config view)"; exit 2; }
CODE="$(ls "$DIR"/*.py 2>/dev/null | head -1)"
[ -n "$CODE" ] || { echo "no *.py in $DIR"; exit 2; }
TITLE="${TITLE:-$SLUG}"

# 1. kernel-metadata.json (offline competition kernel).
#    machine_shape (exact-case!) selects the accelerator; overrides the enable_gpu default (P100).
MSHAPE=""; [ -n "$ACC" ] && MSHAPE="  \"machine_shape\": \"$ACC\","
cat > "$DIR/kernel-metadata.json" <<JSON
{
  "id": "$USER/$SLUG",
  "title": "$TITLE",
  "code_file": "$(basename "$CODE")",
  "language": "python",
  "kernel_type": "script",
  "is_private": true,
  "enable_gpu": $GPU,
$MSHAPE
  "enable_internet": false,
  "competition_sources": ["$COMP"],
  "dataset_sources": [],
  "kernel_sources": []
}
JSON
[ -n "$ACC" ] && echo "   accelerator: machine_shape=$ACC (exact-case)"
echo "== pushing kernel $USER/$SLUG (comp=$COMP) =="
$KAGGLE kernels push -p "$DIR" 2>&1 | grep -v libtinfo || { echo "push failed"; exit 1; }

# 2. poll status until complete
echo "== polling kernel status (offline run can take a while) =="
for i in $(seq 1 120); do
  sleep 30
  st="$($KAGGLE kernels status "$USER/$SLUG" 2>/dev/null | tr -d '\r' | grep -oiE 'complete|error|running|queued|cancel[a-z]*' | head -1)"
  echo "  [$i] status=$st"
  case "$st" in
    complete) echo "KERNEL COMPLETE"; break;;
    error|cancelacknowledged|cancelrequested) echo "KERNEL FAILED ($st) — check: $KAGGLE kernels logs $USER/$SLUG"; exit 1;;
  esac
done
[ "$PUSH_ONLY" = "1" ] && { echo "push-only: kernel ran; submit its output to the competition via the notebook 'Submit' (or ph browser)."; exit 0; }

# 3. submit the kernel output to the competition
echo "== submitting kernel output to $COMP =="
$KAGGLE competitions submit -c "$COMP" -k "$USER/$SLUG" -m "prizehunter kernel $SLUG" 2>&1 | grep -v libtinfo \
  || echo "NOTE: if -k is unsupported for this comp, submit the kernel output via the notebook UI (ph browser) — the kernel run is done and holds submission.csv."
echo "next → kaggle competitions submissions -c $COMP  (verify score)"
