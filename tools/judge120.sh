#!/usr/bin/env bash
# judge120.sh — EVOLUTIONARY_RECIPE Phase 4: the 120% ADVERSARIAL JUDGE GATE.
#
# recipe: "상위권을 넘어 #1에 도달하려면 '무난함'을 타파해야 한다. 위 질문에 완벽히 답하지 못하면 제출 승인
# (Founder Gate)을 열지 않고, 기각 사유를 달아 Phase 1으로 되돌린다."
#
# So a JUDGED-type deliverable does NOT reach the founder's confirm queue on "it's finished". It must first
# survive an adversarial judge that asks the only two questions a prize jury actually answers:
#   1) 이 결과물은 다른 100팀의 평범한 접근과 무엇이 다른가?
#   2) 심사위원을 3초 만에 매료시킬 비대칭적 강점(unfair advantage)이 있는가?
# PASS -> writes .runs/confirm_<key>.pending (the founder gate opens).
# FAIL -> writes <campaign>/JUDGE120_REJECTION.md with the reasons and does NOT open the gate.
#
# usage: judge120.sh <key> <campaign_dir> [artifact_path...]
#        PH_AGENT_CMD='<cli with {PROMPT}>' (default codex)
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; ROOT="$(cd "$CT/.." && pwd)"
KEY="${1:?key}"; DIR="${2:?campaign_dir}"; shift 2 || true
ARTS="$*"; REL="${DIR#$ROOT/}"
AGENT="${PH_AGENT_CMD:-codex exec --skip-git-repo-check -c model_reasoning_effort=high {PROMPT}}"
LOG="$R/judge120_${KEY}.log"; VERDICT="$R/judge120_${KEY}.verdict"
[ -z "$ARTS" ] && ARTS="$(ls "$DIR"/*.pdf "$DIR"/*.md "$DIR"/*.html 2>/dev/null | head -6 | tr '\n' ' ')"
rm -f "$VERDICT"
cd "$ROOT" || exit 1

# The prompt is built with an INTERPOLATING heredoc, not a double-quoted string. A peer found that the
# compliance text I added contained unescaped inner quotes ("ready", "분량은 10쪽 이내") which terminated the
# assignment early: the remainder was executed as shell and P was never set, so under `set -u` this gate
# died at first use — writing NOTHING to its log. A broken gate then looks exactly like "not run yet".
# `bash -n` cannot catch that, hence the PH_SELFTEST hook below (ph doctor exercises it).
P="$(cat <<EOF
You are the 120% ADVERSARIAL JUDGE for our entry in '$KEY' (dir: $REL). You are NOT a helpful reviewer — you
are the jury member who has already seen 100 competent entries today and is looking for a reason to reject.

ARTIFACTS TO JUDGE: $ARTS  (read them; also read $REL/RECON.md for the competition's actual judging criteria)

■ PHASE 0 — COMPLIANCE (mechanical, and it OUTRANKS everything below).
An administratively excluded entry scores ZERO no matter how brilliant it is. Forestry proved this the hard way:
the deliverable we called "ready" was ~2x over an explicit "분량은 10쪽 이내" ceiling and missed a "마이크로데이터
필수" requirement — both stated verbatim in the 공고, neither checked by this gate.
So FIRST: locate the competition's OWN rules (the 공고문/요강/양식 files in this campaign dir or its RECON.md; if
they are not present, fetch/read them) and extract EVERY hard constraint VERBATIM with its source, then check our
artifact against each one:
  - 분량/페이지/글자 수 limits — and whether 도표/이미지/부록 count toward them
  - REQUIRED data sources or methods (필수 vs 권장/등 활용 — the wording decides)
  - 양식 sections that must exist, in order, with the prescribed headings
  - 서명/인/신청서/동의서 attachments, and who must sign
  - file format / packaging (single ZIP? naming?) and submission channel + exact deadline time
  - eligibility (자격, 중복지원 금지, 팀 규모) 
For each: QUOTE the rule, then state our artifact's actual measured value (page count, presence, section names)
and PASS/FAIL. Measure — do not assume ("looks about right" is not a measurement).

■ PHASE 1 — DIFFERENTIATION. Answer the only two questions that decide a prize:
1) **차별성**: What does this do that the other 100 competent entries do NOT? Name it in one sentence. If the
   answer is 'it is well made / thorough / uses AI', that is a REJECT — competence is the floor, not the edge.
2) **비대칭적 강점**: Is there something that grabs a judge within 3 seconds — a result, an image, a number, a
   demo, a reframing — that they cannot get from any other entry? Quote the exact element and where it appears.
Then check the disqualifiers: does it satisfy the stated judging criteria and eligibility, is every claim
verifiable (no overclaim — an inflated claim loses more juries than a modest one), and is the craft at product
grade (a jury reads polish as respect)?

VERDICT — write these as the LAST TWO lines of your reply, in this order:
  COMPLIANCE: PASS  |  COMPLIANCE: FAIL: <each violated rule, quoted, with our measured value and the fix>
  VERDICT: PASS: <the one-sentence differentiator>  |  VERDICT: FAIL: <top 2-3 defects, each with its fix>
The founder gate opens ONLY if BOTH lines are PASS. Default to FAIL on either when uncertain; a compliance FAIL is
strictly more urgent than a differentiation FAIL because it zeroes the entry regardless of quality. Also write your full reasoning to
$REL/JUDGE120_REVIEW.md. Be specific about artifacts and line/section references — a generic critique is useless.
EOF
)"

# SELF-TEST: assemble the prompt and exit. `ph doctor` calls this so a silent prompt-assembly break is
# caught mechanically instead of by a confused human reading an empty log.
if [ "${PH_SELFTEST:-0}" = "1" ]; then
  n=${#P}
  if [ "$n" -lt 500 ]; then echo "  ⛔ judge120 SELFTEST: prompt assembled to only ${n} chars"; exit 1; fi
  echo "  ✓ judge120 SELFTEST: prompt assembles (${n} chars)"; exit 0
fi

echo "  ⚖ judge120 [$KEY]: adversarial jury pass over: $ARTS"
# JUDGE-QUALIFIED SUBSTRATES ONLY — `local` is EXCLUDED on purpose. Measured 2026-07-26: with codex/agy
# exhausted the chain fell to local qwen3-coder, which returned a confident FAIL claiming 14 pages (actual 7),
# two missing sections (all five present) and a statistic absent from the document. A hallucinated FAIL is as
# expensive as a false PASS — it invites tearing up sound work. If no qualified judge is reachable, this gate
# FAILS CLOSED with that reason rather than accepting an unqualified verdict.
printf '%s' "$P" > "$R/.prompt_judge_$KEY"
sub="$(PH_AGENT_CHAIN="${PH_JUDGE_CHAIN:-codex,agy,claude}" bash "$CT/tools/agent_run.sh" "$LOG" "$R/.prompt_judge_$KEY" | grep -oE 'SUBSTRATE=[a-z]+' | cut -d= -f2)"
echo "  judge substrate: ${sub:-none}"
if [ -z "$sub" ] || [ "$sub" = "none" ]; then
  printf 'COMPLIANCE: FAIL: no qualified judge substrate available\nVERDICT: FAIL: no qualified judge substrate available (local models are not accepted as this gate)\n' >> "$LOG"
fi
c="$(grep -oE 'COMPLIANCE:\s*(PASS|FAIL).*' "$LOG" | tail -1)"
v="$(grep -oE 'VERDICT:\s*(PASS|FAIL).*' "$LOG" | tail -1)"
[ -z "$v" ] && v="$(grep -oE '^(PASS|FAIL):.*' "$LOG" | tail -1)"
if [ -z "$c" ]; then
  echo "  ⚠ judge120 [$KEY]: no COMPLIANCE line — treating as FAIL (an unchecked rule is a disqualification risk)"
  c="COMPLIANCE: FAIL: judge produced no compliance verdict"
fi
if [ -z "$v" ]; then
  echo "  ⚠ judge120 [$KEY]: no verdict line found — treating as FAIL (no gate opens on ambiguity)"
  v="VERDICT: FAIL: judge produced no parseable verdict"
fi
# compliance outranks differentiation: a rule violation zeroes the entry, so it closes the gate by itself
case "$c" in *FAIL*) v="FAIL: [COMPLIANCE BLOCK] ${c#COMPLIANCE: } || differentiation said: ${v}";; esac
v="${v#VERDICT: }"
printf '%s\n' "$v" > "$VERDICT"
case "$v" in
  PASS:*)
    printf 'ready\t%s\t%s\n' "judge120 PASS — ${v#PASS: }" "$(date -u +%FT%TZ 2>/dev/null)" > "$R/confirm_${KEY}.pending"
    echo "  ✅ judge120 [$KEY]: PASS → founder confirm gate OPENED"; echo "     ${v#PASS: }";;
  *)
    { echo "# judge120 REJECTION — $KEY ($(date -u +%FT%TZ 2>/dev/null))"; echo; echo "$v"; echo;
      echo "Gate NOT opened. Fix the defects above and re-run: tools/judge120.sh $KEY $DIR"; } > "$DIR/JUDGE120_REJECTION.md"
    echo "  ⛔ judge120 [$KEY]: FAIL → gate stays CLOSED (see $REL/JUDGE120_REJECTION.md)"; echo "     ${v#FAIL: }";;
esac
