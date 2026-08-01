#!/usr/bin/env bash
# name_organ.sh — THE NAMING ORGAN.  (founder 2026-08-01:
#   "새로운 것을 창발해내는 데에는 '명명(naming)'과 의미부여에 있어. 단순히 데이터속에만 매몰되지 않도록.")
#
# WHY THIS EXISTS, measured, not asserted: the no-human test (NO_HUMAN_TEST.md, v2 verdict) showed a loop that
# generated 20+ variants and improved 7.44e-7→7.20e-7 — but every variant was a REPARAMETRIZATION of one
# unnamed framing, and the single time it reached to reframe (round-6 self_consult) the heterogeneous lane was
# down and it produced "none". It stayed 데이터에 매몰. It could optimize WITHIN a name it never made explicit,
# and could not NAME its way out.
#
# consult.sh already asks "what are we assuming that is false?" and collects answers. The naming organ does the
# thing consult does NOT: it forces MEANING-ATTRIBUTION with an anti-renaming gate —
#   1. NAME THE RUT      — from our OWN ledger, name the framing every attempt shares + its structural blind spot.
#                          (mechanical seed → substrate refinement; the mechanical part CANNOT fail, so even in a
#                           total substrate outage the loop at least learns the name of its own trap.)
#   2. NAME THE RESIDUAL — heterogeneous voices (codex, agy, local — NEVER a same-weights fork, which shares our
#                          blind spots and would only RENAME) each name the phenomenon living in the residual:
#                          what KIND of thing the data shows that the framing cannot see. A name + a meaning,
#                          not a parameter.
#   3. WITNESS GATE      — the CLAUDE.md novelty test, made a checklist a judge applies (author≠reviewer):
#                          (a) reduce to the 3 nearest existing framings — if it IS one of them re-labeled, it is
#                              a RENAMING and is rejected LOUDLY (kept visible, never hidden);
#                          (b) the residual invariant it leaves after that reduction;
#                          (c) ONE falsifiable predicted consequence + the <1h/1-box measurement that settles it.
#   4. ORTHOGONAL FRAME  — the surviving witnessed name is written to BRIEF_BANK ## COMP:<key> as a new FRAMING
#                          directive (not a parameter), its predicted consequence becoming the next cheap probe.
#                          This is where 의미부여 redirects generation instead of feeding it another data point.
#
# ROBUSTNESS (the round-6 fix): substrate outages are surfaced as a FIRST-CLASS result, never as silent "none".
# The organ proceeds with whoever answered and marks single-substrate output as weak.
#
#   name_organ.sh propose <key>          fan the rut+residual naming to codex/agy/local → NAMING_<key>_rN.md
#   name_organ.sh judge   <key>          apply the witness gate to the last round (headless claude judge)
#   name_organ.sh gate    <key>          PRINT the witness-gate prompt (for a main-context judge, e.g. /name)
#   name_organ.sh frame   <key> "<name>: <predicted consequence>"   write a survivor as an orthogonal frame
#   name_organ.sh run     <key>          propose → judge → (auto-frame the top survivor)
#   name_organ.sh log     <key>          the naming dialogue so far
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; mkdir -p "$R"
CMD="${1:-}"; KEY="${2:-}"
[ -z "$CMD" ] || [ -z "$KEY" ] && { sed -n '/name_organ.sh propose/,/name_organ.sh log/p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

AGY_MODEL="${PH_AGY_MODEL:-gemini-3.1-pro}"; AGY_EFFORT="${PH_AGY_EFFORT:-high}"
HUB="${COUNCIL_HUB:-$HOME/workspaces/jaewon/council/hub.py}"
DIR="$(PH_TOOLS="$CT/tools" python3 - "$KEY" <<'PY'
import os,sys
sys.path.insert(0, os.environ.get("PH_TOOLS",""))
try:
    from gap_view import resolve_dir
    print(resolve_dir(sys.argv[1]) or "")
except Exception:
    print("")
PY
)"
WORK="${DIR:-$CT}"; LOG="$WORK/NAMING_LOG.md"
rounds(){ ls "$R/naming_${KEY}_r"*.md 2>/dev/null | wc -l | tr -d ' '; }
last_round_file(){ ls -1 "$R/naming_${KEY}_r"*.md 2>/dev/null | sort -V | tail -1; }

# ── the rut, extracted mechanically from our OWN record (this can never fail) ─────────────────────────────────
rut_seed(){
  python3 - "$CT" "$KEY" "${DIR:-}" <<'PY'
import os,sys,glob,re,collections
CT,key,d = sys.argv[1],sys.argv[2],sys.argv[3]
out=[]
# registry position (same axis as #1)
reg=os.path.join(CT,"portfolio_registry.tsv"); cols=[]; row=None
if os.path.exists(reg):
    for l in open(reg,encoding="utf-8",errors="replace"):
        if l.startswith("#   ") and l[4:5].isalpha() and len(l.split())>1: cols.append(l.split()[1])
        elif not l.startswith("#"): break
    for l in open(reg,encoding="utf-8",errors="replace"):
        if l.startswith("#") or not l.strip(): continue
        f=l.rstrip("\n").split("\t")
        if f and f[0]==key: row=dict(zip(cols,f)); break
if row:
    g=lambda k:(row.get(k) or "").strip()
    out.append("POSITION: metric=%s dir=%s best=%s #1=%s"%(g("metric"),g("direction"),g("best"),g("rank1")))
    try:
        b,r1=float(g("best")),float(g("rank1"))
        if b and r1: out.append("  gap-to-#1 (same axis): %.3gx"%((b/r1) if g("direction")=="min" else (r1/b)))
    except ValueError: pass
# the RUT: what every recent attempt shares (filename tokens are a crude but honest fingerprint of the framing)
toks=collections.Counter()
attempts=[]
if d and os.path.isdir(d):
    for p in sorted(glob.glob(os.path.join(d,"variants","*.py")))+sorted(glob.glob(os.path.join(d,"**","experiments","*.py"),recursive=True)):
        n=os.path.basename(p); attempts.append(n)
        for t in re.split(r"[_\-.0-9]+", n.lower()):
            if len(t)>=4 and t not in ("submission","final","py"): toks[t]+=1
    led=os.path.join(d,"iterate_ledger.tsv")
    if os.path.exists(led):
        rows=[l.rstrip("\n").split("\t") for l in open(led,encoding="utf-8") if not l.startswith("#") and l.strip()]
        out.append("ATTEMPTS ON RECORD: %d variants, %d ledger entries"%(len(attempts),len(rows)))
        out.append("RECENT (scale col matters — local≠graded):")
        for f in rows[-8:]: out.append("  "+" | ".join(f[:6]))
common=[f"{t}×{c}" for t,c in toks.most_common(12) if c>=2]
if common: out.append("SHARED VOCABULARY across attempts (the crude fingerprint of the unnamed framing): "+", ".join(common))
if attempts: out.append("SAMPLE ATTEMPT NAMES: "+", ".join(attempts[-12:]))
# our own written framing, if any
for name in ("FRAME.md","VIEW/FINDINGS.md","GAP_REPORT.md"):
    p=os.path.join(d or "",name)
    if p and os.path.exists(p): out.append("FROM OUR OWN %s:\n%s"%(name, open(p,encoding="utf-8",errors="replace").read()[:900]))
print("\n".join(out))
PY
}

PROPOSE_TASK='You are one independent voice on a NAMING panel. Do NOT propose parameters to tune or another
variant of what has been tried — that is the trap we are escaping. Your job is MEANING-ATTRIBUTION:

1. NAME THE RUT. In <=6 words, name the single framing ALL of the attempts above secretly share (as if it were
   a textbook method). Then state its STRUCTURAL blind spot: the one kind of structure it cannot represent BY
   CONSTRUCTION, no matter how it is parametrized.
2. NAME THE RESIDUAL. Name the phenomenon that lives in what the framing cannot see — the thing the data is
   showing but this framing is blind to. Give it a NAME and one line of MEANING (what KIND of object it is:
   a symmetry, a coupling, a conserved quantity, a phase, a hidden variable, …). Not "add term X".
3. WITNESS it yourself so a skeptic cannot dismiss it as a renaming:
   (a) the 3 NEAREST existing framings, and why your name is not merely one of them relabeled;
   (b) the residual INVARIANT your name leaves after that reduction;
   (c) ONE falsifiable PREDICTED CONSEQUENCE and the measurement (<1 hour, one CPU box) that would settle it.
Label guesses as guesses. If our reading of the metric/target/harness is itself the wrong frame, say THAT
first and loudly — a wrong frame named is worth more than a right parameter found.'

voice(){  # voice <label> <cmd...> ; prints a fenced block, surfaces outage as a first-class DEGRADED line
  local label="$1"; shift
  printf '\n### VOICE: %s\n' "$label"
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  out="$(printf '%s' "$out" | grep -v "libtinfo.so.6")"
  if [ $rc -ne 0 ] || printf '%s' "$out" | grep -qiE "quota|rate.?limit|unauthor|forbidden|auth|usage limit|exceeded"; then
    printf '⚠ DEGRADED(%s, rc=%s): %s\n' "$label" "$rc" "$(printf '%s' "$out" | head -3 | tr '\n' ' ' | cut -c1-240)"
    return 1
  fi
  printf '%s\n' "$out"; return 0
}
call_codex(){ timeout "${PH_NAME_TIMEOUT:-420}" codex exec --skip-git-repo-check "$1" </dev/null; }  # </dev/null: exec waits on stdin even with a prompt arg
call_agy(){   timeout "${PH_NAME_TIMEOUT:-420}" agy --dangerously-skip-permissions --model "$AGY_MODEL" --effort "$AGY_EFFORT" -p "$1"; }
call_hub(){   [ -f "$HUB" ] && timeout "${PH_NAME_TIMEOUT:-420}" python3 "$HUB" ask "$1" "$2"; }

cmd_propose(){
  local n f seed P live=0
  n="$(( $(rounds) + 1 ))"; f="$R/naming_${KEY}_r${n}.md"
  seed="$(rut_seed)"
  P="$(printf 'A live competition where we are measurably behind and STUCK IN ONE FRAMING. Our own measured record:\n\n%s\n\n%s' "$seed" "$PROPOSE_TASK")"
  printf '%s' "$P" > "$R/.naming_prompt_${KEY}"
  echo "  🏷  naming round $n — fanning to heterogeneous voices ($(printf '%s' "$P" | wc -c) chars of OUR record)"
  {
    printf '## NAMING ROUND %s — %s\n\n### RUT (mechanical, from our own record — cannot fail)\n%s\n' "$n" "$(date -u +%FT%TZ)" "$seed"
    # heterogeneous ONLY — codex (GPT prior), agy (Gemini/Google prior), council/local. Never a same-weights fork.
    voice "codex (GPT-5.x, independent prior)" call_codex "$P" && live=$((live+1))
    voice "agy (Gemini $AGY_MODEL, grounded)"  call_agy   "$P" && live=$((live+1))
    if [ -f "$HUB" ]; then voice "council:deepseek" call_hub deepseek-api "$P" && live=$((live+1)); fi
    printf '\n### PANEL HEALTH\n%s heterogeneous voice(s) answered.' "$live"
    [ "$live" -eq 0 ] && printf '  🔴 NAMING LANE DOWN — no external voice answered. The RUT above still stands (mechanical); treat any single-context naming as WEAK and retry when a substrate returns.\n'
    [ "$live" -eq 1 ] && printf '  ⚠ single-substrate — ~1 effective vote; a name here is a hypothesis, not a consensus.\n'
  } > "$f"
  { echo; cat "$f"; } >> "$LOG"
  echo "  → $f ($(wc -c < "$f") bytes) · $live live voice(s)"
  echo "  next → ph name judge $KEY   (apply the witness gate; renamings are rejected)"
}

GATE='You are the WITNESS JUDGE — a DIFFERENT context from the voices that proposed these names (author≠reviewer).
For EACH named phenomenon proposed above, rule it WITNESSED or RENAMING, and show your work:
- RENAMING (reject, loudly) if it reduces to one of the 3 nearest existing framings with nothing left over —
  a new label on an old object. Say which framing it collapses into.
- WITNESSED (keep) only if it survives that reduction AND leaves a residual invariant AND carries ONE
  falsifiable predicted consequence with a <1h/1-box measurement. A name with no predicted consequence is a
  vibe, not a witness — reject it.
Then RANK the witnessed names by (score they would explain × cheapness of the decisive test), and for the #1,
write the ORTHOGONAL FRAME as a single directive line beginning "FRAME:" that tells the generator what NEW kind
of construction to build (not a parameter). End with exactly one line:  ADOPT: <name>: <predicted consequence>
(or  ADOPT: none — every candidate was a renaming)  so the organ can act on your verdict mechanically.'

cmd_gate(){ local f; f="$(last_round_file)"; [ -z "$f" ] && { echo "no naming round yet — run: ph name propose $KEY"; return 1; }
  printf '%s\n\n=== THE NAMED CANDIDATES TO JUDGE ===\n%s\n' "$GATE" "$(cat "$f")"; }

cmd_judge(){  # headless judge = a claude session (separate context), for the autonomous loop path
  local f; f="$(last_round_file)"; [ -z "$f" ] && { echo "no naming round yet — run: ph name propose $KEY"; return 1; }
  echo "  ⚖  witness gate (headless claude judge, separate context) on $(basename "$f")"
  local verdict; verdict="$(bash "$CT/tools/session_agent.sh" ask "$KEY" judge "$(cmd_gate)" 2>&1 | grep -v "libtinfo.so.6")"
  printf '\n## WITNESS VERDICT — %s\n%s\n' "$(date -u +%FT%TZ)" "$verdict" >> "$LOG"
  printf '%s\n' "$verdict"
  local adopt; adopt="$(printf '%s' "$verdict" | grep -iE '^ADOPT:' | tail -1 | sed 's/^[Aa][Dd][Oo][Pp][Tt]:[[:space:]]*//')"
  if [ -n "$adopt" ] && ! printf '%s' "$adopt" | grep -qi '^none'; then
    echo "  → witnessed survivor: $adopt"; cmd_frame "$adopt"
  else
    echo "  → gate returned no survivor (all renamings, or lane too weak). RUT is still named; retry propose when substrates return."
  fi
}

cmd_frame(){  # write the surviving witnessed name as an ORTHOGONAL framing directive the generator will read
  local nm="${1:?ph name frame <key> \"<name>: <predicted consequence>\"}"
  local bank="${PH_BRIEF_BANK:-$CT/BRIEF_BANK.md}"
  [ -f "$bank" ] || printf '# BRIEF_BANK — drive briefs + steers\n' > "$bank"
  grep -q "^## COMP:$KEY\$" "$bank" || printf '\n## COMP:%s\n' "$KEY" >> "$bank"
  python3 - "$bank" "$KEY" "- [NAMED $(date -u +%FT%TZ)] ORTHOGONAL FRAME (witnessed, not a parameter): $nm" <<'PY'
import sys
bank,key,line=sys.argv[1],sys.argv[2],sys.argv[3]
src=open(bank,encoding="utf-8").read().split("\n"); hdr=f"## COMP:{key}"
for i,l in enumerate(src):
    if l.strip()==hdr: src.insert(i+1,line); break
open(bank,"w",encoding="utf-8").write("\n".join(src))
PY
  echo "  🧭 orthogonal frame written to BRIEF_BANK ## COMP:$KEY — the next generation round reads it as a NEW framing, not a parameter."
  echo "     $nm"
}

case "$CMD" in
  propose) cmd_propose ;;
  gate)    cmd_gate ;;
  judge)   cmd_judge ;;
  frame)   cmd_frame "${3:-}" ;;
  run)     cmd_propose && cmd_judge ;;
  log)     [ -f "$LOG" ] && cat "$LOG" || echo "no naming log yet for $KEY" ;;
  *) echo "unknown: $CMD (propose|gate|judge|frame|run|log)"; exit 2 ;;
esac
