#!/usr/bin/env bash
# preflight.sh — MANDATORY PRE-SUBMISSION CHECKLIST + LOGGED HUMAN CONFIRMATION.
#
# council (deepseek, 2026-07-26) named the single thing that turns this system from a product into a liability:
#   "A user submits a disqualifiable or rule-breaking entry BECAUSE your system told them it was ready."
# The cheapest guard is NOT more self-auditing — it is putting the competition's LITERAL rules in front of a human
# and recording that they confirmed each one. We nearly shipped exactly this failure today: forestry's deliverable
# was called "ready" while it was ~2x over an explicit 10-page limit and missing a mandatory data source.
#
#   preflight.sh show <key>            print the checklist (rules pulled from the campaign's own record) — dry, safe
#   preflight.sh confirm <key>         interactive: each rule must be answered y, then the literal words I CONFIRM
#   preflight.sh status <key>          has this key been confirmed, and for which artifact fingerprint
#
# A confirmation is bound to the ARTIFACT FINGERPRINT (sha256 of the files listed), so changing the deliverable
# after confirming invalidates it — you cannot confirm one thing and ship another (the SHIP≠VALIDATE lesson).
# Log: PREFLIGHT_LOG.jsonl (append-only). Nothing here submits anything; it only gates.
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; ROOT="$(cd "$CT/.." && pwd)"
LOG="$CT/PREFLIGHT_LOG.jsonl"
CMD="${1:-}"; KEY="${2:-}"
[ -z "$KEY" ] && { echo "usage: preflight.sh show|confirm|status <key>"; exit 2; }
# DIR RESOLUTION — exact → evolve_map → longest-token fuzzy. The naive "${KEY%%-*}" glob resolved
# 2026-forestry-statistics to a campaign named 202604180003 (it matched on "2026"), which is the same
# mis-routing class a peer reported in guess_dir. A checklist built from the wrong campaign is worse than none.
DIR=""
[ -d "$CT/campaigns/$KEY" ] && DIR="$CT/campaigns/$KEY"
if [ -z "$DIR" ] && [ -f "$R/evolve_map.tsv" ]; then
  DIR="$(awk -F'\t' -v k="$KEY" '$1==k{print $2; exit}' "$R/evolve_map.tsv" 2>/dev/null)"
  [ -n "$DIR" ] && [ ! -d "$DIR" ] && DIR=""
fi
if [ -z "$DIR" ]; then
  tok="$(printf '%s' "$KEY" | tr '_' '-' | tr '-' '\n' | awk '{ if (length($0)>length(m) && $0 !~ /^[0-9]+$/) m=$0 } END{print m}')"
  [ -n "$tok" ] && DIR="$(ls -d "$CT/campaigns/"*"$tok"* 2>/dev/null | head -1)"
fi
[ -z "$DIR" ] && { echo "campaign dir not found for '$KEY'"; exit 1; }

# rules are read from the campaign's OWN record — never invented here
rules_file(){ for f in "$DIR/SUBMIT_GUIDE.md" "$DIR/RECON.md" "$DIR/FRAME.md"; do [ -f "$f" ] && { echo "$f"; return; }; done; }
artifacts(){ ls "$DIR"/*.pdf "$DIR"/*.zip "$DIR"/*.hwpx "$DIR"/*.mp4 "$DIR"/REPORT_FINAL.* 2>/dev/null | head -12; }
fingerprint(){ artifacts | while read -r f; do [ -f "$f" ] && printf '%s  %s\n' "$(sha256sum "$f" 2>/dev/null | cut -c1-16)" "$(basename "$f")"; done; }

extract_rules(){
  rf="$(rules_file)"
  [ -z "$rf" ] && { echo "NO RULE RECORD FOUND — a checklist cannot be built from nothing. Fetch the 공고/rules into $DIR first."; return 1; }
  echo "# rules quoted from $(basename "$rf") (verify against the official 공고 before relying on them):"
  grep -nEi '분량|쪽|페이지|필수|양식|서식|서명|제출|마감|deadline|format|zip|page|limit|required|eligib|자격|중복' "$rf" 2>/dev/null \
    | head -14 | sed 's/^/    /'
}

case "$CMD" in
  show)
    echo "== PRE-FLIGHT [$KEY] =="
    extract_rules || true
    echo
    echo "# artifacts that would be submitted (fingerprint):"
    fp="$(fingerprint)"; [ -z "$fp" ] && echo "    ⛔ NO ARTIFACT FOUND in $DIR — there is nothing to submit yet" || printf '%s\n' "$fp" | sed 's/^/    /'
    echo
    echo "# the six questions a jury/administrator answers first (you must answer each):"
    cat <<'EOF'
    1. 분량/형식 규정을 실제로 측정해 충족하는가 (페이지 수를 세었는가, 도표가 분량에 포함되는가)
    2. 필수 데이터/방법/증빙을 실제로 사용했는가 (권장이 아니라 '필수'로 적힌 것)
    3. 공식 양식·서식·서명(인)이 요구대로 채워졌는가
    4. 제출 채널과 마감 시각이 정확한가 (이메일 vs 포털, 시:분, 타임존)
    5. 자격·중복지원 규정을 위반하지 않는가
    6. 모든 주장이 검증 가능한가 (과장된 문구 하나가 심사를 잃는다)
EOF
    echo "→ to proceed: ph preflight confirm $KEY   (nothing is sent; it records your confirmation)"
    ;;

  confirm)
    fp="$(fingerprint)"
    [ -z "$fp" ] && { echo "⛔ no artifact in $DIR — nothing to confirm"; exit 1; }
    echo "== PRE-FLIGHT CONFIRM [$KEY] =="; extract_rules || true
    echo; echo "artifact fingerprint:"; printf '%s\n' "$fp" | sed 's/^/    /'; echo
    qs=("분량/형식 규정을 실측해 충족" "필수 데이터/방법/증빙을 실제 사용" "공식 양식·서식·서명 완비" "제출 채널·마감 시각 정확" "자격·중복지원 규정 위반 없음" "모든 주장이 검증 가능(과장 없음)")
    for q in "${qs[@]}"; do
      printf '  [ ] %s  (y/n) ' "$q"; read -r a </dev/tty || a=n
      case "$a" in y|Y) ;; *) echo "  ⛔ 중단: '$q' 미충족 — 고치고 다시 실행하세요."; exit 1;; esac
    done
    printf '  최종 확인을 위해 대문자로 입력하세요 [I CONFIRM]: '; read -r c </dev/tty || c=""
    [ "$c" != "I CONFIRM" ] && { echo "  ⛔ 확인 문구 불일치 — 기록하지 않았습니다."; exit 1; }
    ts="$(date -u +%FT%TZ 2>/dev/null)"
    fph="$(printf '%s' "$fp" | sha256sum | cut -c1-32)"
    printf '{"key":"%s","at":"%s","fingerprint":"%s","artifacts":%s,"confirmed_by":"founder-tty"}\n' \
      "$KEY" "$ts" "$fph" "$(printf '%s' "$fp" | awk '{printf "\"%s\",",$2}' | sed 's/,$//;s/^/[/;s/$/]/')" >> "$LOG"
    printf '%s\t%s\n' "$fph" "$ts" > "$R/preflight_${KEY}.ok"
    echo "  ✓ 기록됨 → $(basename "$LOG") (fingerprint $fph)"
    echo "  이제 외부 제출을 진행할 수 있습니다. 산출물을 수정하면 이 확인은 무효가 됩니다(지문 불일치)."
    ;;

  status)
    ok="$R/preflight_${KEY}.ok"
    if [ ! -f "$ok" ]; then echo "  $KEY: NOT CONFIRMED — run: ph preflight show $KEY"; exit 1; fi
    saved="$(cut -f1 "$ok")"; now="$(fingerprint | sha256sum | cut -c1-32)"
    if [ "$saved" = "$now" ]; then echo "  $KEY: CONFIRMED $(cut -f2 "$ok") (fingerprint matches)"
    else echo "  ⛔ $KEY: confirmation is STALE — the artifact changed after it was confirmed (saved $saved, now $now). Re-confirm."; exit 1; fi
    ;;
  *) echo "usage: preflight.sh show|confirm|status <key>";;
esac
