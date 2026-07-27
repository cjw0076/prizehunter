#!/usr/bin/env bash
# doctor.sh — MECHANICAL SELF-DIAGNOSIS so any CLI entering this system SEES its structural defects immediately.
#
# founder 2026-07-26: "이런 시스템의 구조적 결함을 CLI가 제대로 파악할 수 있도록 개선."
#
# Every defect that cost us real money today was mechanically detectable, yet was found only by luck and effort:
#   • open_frame's check REJECTED the very format its own prompt mandates ("## VERIFIED TARGET") → the gate was
#     UNSATISFIABLE, so evolve dispatched zero drives while looking busy. (Class: SELF-UNSATISFIABLE GATE)
#   • the substrate chain fell through to `claude` and spent the head agent's own quota. (Class: COST LEAK)
#   • local-scale scores were recorded into LB-scale history = fictitious progress. (Class: SCALE MIXING)
#   • board keys ≠ registry keys → harvested scores landed in orphan state files. (Class: KEY FRAGMENTATION)
#   • a founder gate demanded a submission to a competition that had closed 19 days earlier. (Class: DEAD GATE)
# So this runs FAST (no agents, no network), asserts each machine gate against a SYNTHETIC CONFORMANT input, and
# prints one screen. `ph next` shows its headline so a fresh CLI cannot miss it.
#
#   doctor.sh          full report
#   doctor.sh --brief  one line (used by ph next)
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; ROOT="$(cd "$CT/.." && pwd)"
REG="$CT/portfolio_registry.tsv"; BOARD="$R/autopush_board.tsv"
BRIEF=0; [ "${1:-}" = "--brief" ] && BRIEF=1
CRIT=0; HIGH=0; MED=0; LINES=""
say(){ # say <sev> <class> <msg> [<fix>]
  case "$1" in CRITICAL) CRIT=$((CRIT+1));; HIGH) HIGH=$((HIGH+1));; *) MED=$((MED+1));; esac
  LINES="$LINES\n  [$1] $2 — $3${4:+\n      → fix: $4}"; }
TMP="$(mktemp -d 2>/dev/null || echo /tmp/ph_doctor_$$)"; mkdir -p "$TMP"
trap 'rm -rf "$TMP" 2>/dev/null' EXIT

# ── 1. SELF-UNSATISFIABLE GATES: does each machine check ACCEPT a synthetic, conformant input? ──────────────
mkdir -p "$TMP/camp"
cat > "$TMP/camp/FRAME.md" <<'EOF'
## VERIFIED TARGET
#1 = 1.234, measured 2026-07-26 via the platform CLI.
## HARNESS TRUST
UNKNOWN — the cheapest anchor experiment is X.
## FRAMING 1
a
## FRAMING 2
b
## FRAMING 3
c
## PRIORS
PRIOR: the public split is random | FALSIFY: adversarial validation AUC
EOF
if ! bash "$CT/tools/open_frame.sh" check __doctor__ "$TMP/camp" >/dev/null 2>&1; then
  say CRITICAL "SELF-UNSATISFIABLE GATE" \
    "open_frame.sh check REJECTS a frame that satisfies every rule its own prompt states → the gate can never pass, so evolve drives nothing" \
    "run: bash tools/open_frame.sh check __doctor__ <a conformant frame dir>  and relax the failing pattern"
fi
# judge120's verdict parser: a synthetic PASS/PASS log must open the gate, a COMPLIANCE FAIL must not
printf 'blah\nCOMPLIANCE: PASS\nVERDICT: PASS: real differentiator\n' > "$TMP/j_pass.log"
printf 'blah\nCOMPLIANCE: FAIL: over length\nVERDICT: PASS: nice\n' > "$TMP/j_fail.log"
jp="$(grep -oE 'VERDICT:\s*(PASS|FAIL).*' "$TMP/j_pass.log" | tail -1)"
jc="$(grep -oE 'COMPLIANCE:\s*(PASS|FAIL).*' "$TMP/j_fail.log" | tail -1)"
[ -z "$jp" ] && say CRITICAL "SELF-UNSATISFIABLE GATE" "judge120's VERDICT parser cannot read its own mandated 'VERDICT: PASS:' line" "align the grep with the prompt's stated format"
[ -z "$jc" ] && say CRITICAL "SELF-UNSATISFIABLE GATE" "judge120's COMPLIANCE parser cannot read its own mandated line" "align the grep with the prompt"
# PROMPT-ASSEMBLY BREAKAGE (a class `bash -n` cannot see): a long multilingual prompt held in a double-quoted
# assignment dies silently if it contains an unescaped inner quote — the string ends early, the rest runs as shell,
# the variable is never set, and under `set -u` the tool aborts writing NOTHING. A broken gate then looks exactly
# like "not run yet". judge120 shipped with exactly this defect; a peer session found it, not this doctor.
if ! PH_SELFTEST=1 bash "$CT/tools/judge120.sh" __doctor__ /tmp >/dev/null 2>&1; then
  say CRITICAL "PROMPT ASSEMBLY" "judge120.sh fails its own prompt self-test → the gate is a silent no-op (empty log, no pending, indistinguishable from 'not run')" \
     "PH_SELFTEST=1 bash tools/judge120.sh __doctor__ /tmp   and fix the quoting (use an interpolating heredoc)"
fi
# quote-parity scan: an odd number of unescaped double quotes in a shell tool is a strong smell of the same class
for f in "$CT/tools/"*.sh; do
  b="$(basename "$f")"
  n="$(python3 - "$f" <<'PYQ'
import sys, re
# Count unescaped double quotes OUTSIDE heredoc bodies. Heredocs legitimately contain unbalanced quotes (that is
# exactly why we moved the long prompts into them), so counting them produced a false positive on this very file.
lines = open(sys.argv[1], errors="ignore").read().splitlines()
out, tag = [], None
for ln in lines:
    if tag is None:
        m = re.search(r"<<-?\s*'?([A-Za-z_][A-Za-z0-9_]*)'?", ln)
        if m:
            tag = m.group(1)
            out.append(re.sub(r"<<-?\s*'?[A-Za-z_][A-Za-z0-9_]*'?.*$", "", ln))
            continue
        out.append(ln)
    else:
        if ln.strip() == tag:
            tag = None
print(("\n".join(out)).replace('\\"', '').count('"') % 2)
PYQ
)"
  [ "$n" = "1" ] && say HIGH "PROMPT ASSEMBLY" "$b has an ODD number of unescaped double quotes — likely an early-terminated string (the judge120 failure class)" "grep the long prompt assignments and move them into an interpolating heredoc"
done

# audit_targets must report 0 findings on a synthetic clean registry row (else it cries wolf forever)
if ! python3 "$CT/tools/audit_targets.py" >/dev/null 2>&1; then
  say HIGH "TOOL BROKEN" "audit_targets.py exits non-zero" "run it directly and read the traceback"
fi

# ── 2. KEY FRAGMENTATION + ORPHAN STATE ────────────────────────────────────────────────────────────────────
regkeys="$(awk -F'\t' '!/^#/ && NF>3 && $1!="key" {print $1}' "$REG" 2>/dev/null | sort -u)"
if [ -f "$BOARD" ]; then
  while IFS=$'\t' read -r k rest; do
    case "$k" in ''|'#'*) continue;; esac
    printf '%s\n' "$regkeys" | grep -qx "$k" || say HIGH "KEY FRAGMENTATION" \
      "legacy board key '$k' is not a registry key → anything harvested under it lands in an orphan state file" \
      "rename the board row to its registry key, or retire the board row"
  done < "$BOARD"
fi
for f in "$R"/goal_*.json; do
  [ -e "$f" ] || continue
  k="$(basename "$f" .json)"; k="${k#goal_}"
  printf '%s\n' "$regkeys" | grep -qx "$k" || say HIGH "ORPHAN STATE" \
    "$(basename "$f") has no registry row → its recorded history (and therefore its stall/REFUTE state) is invisible" \
    "merge it into the correct key's history and delete the orphan"
done

# ── 3. SCALE MIXING: score files must declare their axis, or local gains masquerade as leaderboard progress ──
for f in "$R"/drive_*.score; do
  [ -e "$f" ] || continue
  k="$(basename "$f" .score)"; k="${k#drive_}"
  [ -f "$R/drive_${k}.scale" ] || say MED "SCALE MIXING" \
    "drive_${k}.score has no .scale sidecar → the harvester must assume LOCAL and record a flat round" \
    "have the drive write 'lb' or 'local' to .runs/drive_${k}.scale"
done

# ── 4. COST LEAK: is the head agent's own quota reachable by background drives? ─────────────────────────────
chain="${PH_AGENT_CHAIN:-$(grep -oE 'PH_AGENT_CHAIN:-[a-z,]+' "$CT/tools/agent_run.sh" 2>/dev/null | head -1 | cut -d- -f3-)}"
case "$chain" in
  claude,*|*,claude,*) say HIGH "COST LEAK" "substrate chain '$chain' reaches 'claude' before the free substrates → background drives spend the head agent's quota" "put claude LAST (codex,agy,local,claude)";;
esac
cooling=""
for f in "$R"/.substrate_backoff.*; do [ -e "$f" ] || continue; cooling="$cooling $(basename "$f" | sed 's/.*backoff\.//')"; done
[ -n "$cooling" ] && LINES="$LINES\n  [INFO    ] SUBSTRATE — cooling:${cooling} (chain will skip these until they age out)"

# ── 4b. DISK PRESSURE: a full disk corrupts state mid-run (council named this a release blocker) ─────────────
dfree="$(df -PBG "$CT" 2>/dev/null | awk 'NR==2{gsub("G","",$4); print $4+0}')"
dpct="$(df -P "$CT" 2>/dev/null | awk 'NR==2{gsub("%","",$5); print $5+0}')"
if [ -n "$dfree" ] && [ "$dfree" -lt "${PH_DISK_MIN_FREE_GB:-20}" ]; then
  say HIGH "DISK PRESSURE" "only ${dfree}GB free (${dpct}% used) — drives are being refused" "free space or raise PH_DISK_MIN_FREE_GB deliberately"
else
  LINES="$LINES\n  [INFO    ] DISK — ${dfree}GB free (${dpct}% used); guard trips below ${PH_DISK_MIN_FREE_GB:-20}GB (percent alone is a false alarm on a large shared disk)"
fi

# ── 5. DEAD GATES: a founder gate for a competition whose deadline has passed ───────────────────────────────
today="$(date -u +%F 2>/dev/null || echo 2026-01-01)"
cat > "$TMP/deadgate.py" <<'PYX'
import sys, re
reg, today = sys.argv[1], sys.argv[2]
cols = []
for l in open(reg):
    if l.startswith("#   ") and l[4:5].isalpha() and len(l.split()) > 1: cols.append(l.split()[1])
    elif not l.startswith("#"): break
g = lambda f, n: f[cols.index(n)] if n in cols and cols.index(n) < len(f) else ""
for l in open(reg):
    if l.startswith("#") or not l.strip(): continue
    f = l.rstrip("\n").split("\t")
    if g(f, "key") in ("key", ""): continue
    if g(f, "status") in ("lapsed", "settled", "dropped", "closed", "submitted"): continue
    blob = " ".join([g(f, "blocker"), g(f, "next_lever"), g(f, "progress")])
    if not re.search(r"제출|submit|upload|발송|send", blob, re.I): continue
    ds = re.findall(r"20\d\d-\d\d-\d\d", blob)
    past = [d for d in ds if d < today]
    if past and not [d for d in ds if d >= today]:
        print(f"{g(f,'key')}|{max(past)}")
PYX
python3 "$TMP/deadgate.py" "$REG" "$today" > "$TMP/deadgates" 2>/dev/null || : > "$TMP/deadgates"
while IFS='|' read -r k dl; do
  [ -z "$k" ] && continue
  say HIGH "DEAD GATE" "'$k' still demands an external submission but every date in its row is past (latest $dl)" \
     "verify the competition is closed, then settle/lapse the row (orbit-wars carried exactly this defect for 19 days)"
done < "$TMP/deadgates"

# ── 6. FRESHNESS: frames/gaps that exist but have gone stale, and rows with no instruments at all ───────────
nofr=0; nogap=0
for k in $regkeys; do
  d="$(ls -d "$CT/campaigns/"*"${k%%-*}"* 2>/dev/null | head -1)"
  [ -z "$d" ] && continue
  [ -f "$d/FRAME.md" ] || nofr=$((nofr+1))
  [ -f "$d/GAP_REPORT.md" ] || nogap=$((nogap+1))
done
LINES="$LINES\n  [INFO    ] INSTRUMENTS — $nofr live row(s) without a FRAME.md, $nogap without a GAP_REPORT.md (evolve will frame/hunt these before driving)"

# ── 6b. GEOMETRY UNSEEN: live rows that HAVE local data but whose train↔test geometry was never rendered ────
# THE_PATH_TO_NUMBER_ONE.md's "Geometry Blindness": 71 lens runs, all numeric, and nobody ever looked at a
# picture. `ph view <key>` renders it in seconds and has already produced two load-bearing findings (rogii's
# 3-well scored test; numerai's train-constant feature family). So a live row with data and no VIEW is a
# cheap, un-taken probe — and the machine can see that gap even though it cannot see the picture.
unseen=""; nseen=0
for k in $regkeys; do
  d="$(ls -d "$CT/campaigns/"*"${k%%-*}"* 2>/dev/null | head -1)"
  [ -z "$d" ] && continue
  has_data=0
  for pat in "$d/data/train" "$d/data/train.csv" "$d/train.csv" "$d"/*/train.parquet "$d"/data/*/train.parquet "$d"/*/train.csv; do
    [ -e "$pat" ] && has_data=1
  done
  [ "$has_data" = 0 ] && continue
  if [ -f "$d/VIEW/FINDINGS.md" ]; then nseen=$((nseen+1)); else unseen="$unseen $k"; fi
done
n_unseen="$(printf '%s' "$unseen" | wc -w)"
if [ "$n_unseen" -gt 0 ]; then
  say MEDIUM "GEOMETRY UNSEEN" "$n_unseen live row(s) have local train/test data but no rendered view:$unseen" \
     "run: ph view <key>  (seconds; writes VIEW/index.html for your eyes + VIEW/FINDINGS.md into the drive brief)"
else
  [ "$nseen" -gt 0 ] && LINES="$LINES\n  [INFO    ] GEOMETRY — $nseen row(s) with local data have a rendered view (ph view)"
fi

# ── 6c. UNREGISTERED CAMPAIGN: real work on disk with NO registry row = invisible to every loop ─────────────
# Same class as SYSTEM_GAP_REPORT #2 (the cockpit read a 12-row board while 62 competitions existed): the
# registry is the single source of truth, so a campaign missing from it gets no EV allocation, no stall
# detection, no deadline radar — it simply does not exist to the system, however much work sits in its folder.
# Found this way: campaigns/numerai-main holds 6.8M rows of tournament data, artifacts and validation reports,
# and appears in ZERO registry rows. Only dirs with REAL evidence of work are flagged (not pool scaffolds).
unreg=""
for d in "$CT/campaigns/"*/; do
  k="$(basename "$d")"
  grep -qF "$k" "$REG" 2>/dev/null && continue
  evid=0
  for pat in "$d"data/train "$d"data/*.csv "$d"data/*.parquet "$d"*/train.parquet "$d"train.csv; do
    [ -e "$pat" ] && evid=1
  done
  [ "$evid" = 0 ] && continue
  work=0
  for pat in "$d"WORKLOG.md "$d"artifacts "$d"submission*.csv "$d"REPORT*.md; do [ -e "$pat" ] && work=1; done
  [ "$work" = 0 ] && continue
  unreg="$unreg $k"
done

# SPLIT RECORD: a campaign folder holding the competition's OWN record (RECON/PLAN — schema, metric, deadlines)
# that no registry row points at, while a differently-named folder holds the work. Found this way: the rogii
# campaign's RECON.md and PLAN.md sat in campaigns/rogii-wellbore-geology/ for 27 days while every drive ran in
# campaigns/rogii_wellbore/, which had NO recon record at all — so each entry frame was re-derived from scratch.
# The check asks the RESOLVING question: does the folder the registry points at actually HAVE a record?
# Its first form asked "does an orphan folder hold a record" — which stayed true forever after the fix, because
# the fix is to COPY (records are append-only; nothing is deleted). A check that cannot be satisfied by its own
# prescribed fix is the SELF-UNSATISFIABLE class this file exists to catch, so it had to be inverted.
split="$(python3 - "$REG" "$CT" <<'PYS'
import os, sys
reg, CT = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(CT))
REC = ("RECON.md", "PLAN.md", "PLAN.json", "PREP_BASELINE.md")
rows = []
for line in open(reg, encoding="utf-8", errors="replace"):
    if line.startswith("#"):
        continue
    f = line.rstrip("\n").split("\t")
    if len(f) >= 2 and f[0] and f[1]:
        rows.append((f[0], f[1]))
def resolve(p):
    for base in (ROOT, os.path.dirname(CT), CT, ""):
        c = p if os.path.isabs(p) else os.path.join(base, p)
        if os.path.isdir(c):
            return c
    return None
def has_record(d):
    if not d or not os.path.isdir(d):
        return False
    names = os.listdir(d)
    return any(n in REC or n.startswith("CAMPAIGN_") for n in names)
out = []
camp = os.path.join(CT, "campaigns")
for k in sorted(os.listdir(camp)) if os.path.isdir(camp) else []:
    d = os.path.join(camp, k)
    if not os.path.isdir(d) or not has_record(d):
        continue
    tgt = [(rk, rd) for rk, rd in rows if rk == k or rk.replace("-", "_") == k.replace("-", "_")]
    if not tgt:
        continue
    rk, rd = tgt[0]
    dst = resolve(rd)
    if dst and os.path.realpath(dst) == os.path.realpath(d):
        continue                       # the registry points here: nothing is split
    if has_record(dst):
        continue                       # already resolved (the record was copied over)
    out.append("%s→%s" % (k, rd))
print(" ".join(out))
PYS
)"
n_split="$(printf '%s' "$split" | wc -w)"
[ "$n_split" -gt 0 ] && say MEDIUM "SPLIT RECORD" \
  "$n_split campaign record(s) (RECON/PLAN) exist only in a folder the registry does NOT point at:$split" \
  "copy the record into the folder the registry points at — otherwise every entry frame re-derives schema/metric/deadline from scratch"

n_unreg="$(printf '%s' "$unreg" | wc -w)"
[ "$n_unreg" -gt 0 ] && say HIGH "UNREGISTERED CAMPAIGN" \
  "$n_unreg campaign dir(s) hold real data AND real work but have no portfolio_registry.tsv row:$unreg" \
  "add a row (key/dir/metric/direction/best/rank1/status) or archive the folder — with no row it gets zero EV allocation, no stall detection, no deadline radar"

# ── 7. TOOL WIRING: anything ph references that is missing, and new tools ph never exposes ──────────────────
for t in $(grep -ohE 'tools/[a-z_0-9]+\.(sh|py)' "$CT/ph" 2>/dev/null | sort -u); do
  [ -f "$CT/$t" ] || say HIGH "MISSING TOOL" "ph references $t which does not exist" "restore it or drop the verb"
done
unexposed=""
for f in "$CT/tools/"*.sh "$CT/tools/"*.py; do
  b="$(basename "$f")"
  case "$b" in agent_run.sh|brief_render.sh|goal_loop.py|prizehunter_ui.py) continue;; esac
  grep -q "$b" "$CT/ph" 2>/dev/null || unexposed="$unexposed $b"
done
n_unexp="$(printf '%s' "$unexposed" | wc -w)"
[ "$n_unexp" -gt 0 ] && LINES="$LINES\n  [INFO    ] ENTRY SURFACE — $n_unexp tool(s) not reachable from \`ph\` (a capability invisible at the entry surface gets re-invented; run: ph help)"

# ── output ─────────────────────────────────────────────────────────────────────────────────────────────────
if [ "$BRIEF" = 1 ]; then
  if [ $((CRIT+HIGH)) -gt 0 ]; then echo "⚕ doctor: CRITICAL=$CRIT HIGH=$HIGH MED=$MED — run \`ph doctor\` (a structural defect silently voids drives)"
  else echo "⚕ doctor: clean (MED=$MED)"; fi
  exit 0
fi
echo "== ph doctor — mechanical self-diagnosis ($(date -u +%FT%TZ 2>/dev/null)) =="
echo "   classes: SELF-UNSATISFIABLE GATE · KEY FRAGMENTATION · ORPHAN STATE · SCALE MIXING · COST LEAK · DEAD GATE"
printf '%b\n' "$LINES"
echo "== CRITICAL=$CRIT · HIGH=$HIGH · MEDIUM=$MED =="
[ $((CRIT+HIGH)) -gt 0 ] && echo "   a CRITICAL here means a gate/loop is structurally dead — fix it before trusting any drive result."
exit 0
