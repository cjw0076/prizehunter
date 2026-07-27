#!/usr/bin/env bash
# package_submission.sh — zip a competition's COMPLETED submission materials plus an
# auto-generated founder guide, ready to email for confirmation (prizehunter standard).
# Nothing outward-facing happens here; this only builds a local package + guide.
#   usage: package_submission.sh --key <K> [--dir <submission_dir>] [--out <zip_path>] [--email-safe|--portal-full]
set -euo pipefail
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"          # control_tower
ROOT="$(cd -- "$PH_HOME/../.." && pwd)"                 # dacon repo root
REG="$PH_HOME/portfolio_registry.tsv"
DATE="$(date +%Y%m%d)"

key=""; subdir=""; out=""; package_mode="portal-full"
while [ $# -gt 0 ]; do case "$1" in
  --key) key="$2"; shift 2;;
  --dir) subdir="$2"; shift 2;;
  --out) out="$2"; shift 2;;
  --email-safe) package_mode="email-safe"; shift;;
  --portal-full) package_mode="portal-full"; shift;;
  *) echo "unknown arg: $1" >&2; exit 2;;
esac; done
[ -n "$key" ] || { echo "usage: package_submission.sh --key <K> [--dir D] [--out Z]" >&2; exit 2; }

# pull this competition's row from the registry (single source of truth)
row="$(awk -F'\t' -v k="$key" '$1==k{print; exit}' "$REG")"
[ -n "$row" ] || { echo "key '$key' not in registry" >&2; exit 1; }
cdir="$(printf '%s' "$row" | cut -f2)"
blocker="$(printf '%s' "$row" | cut -f10)"
nextlev="$(printf '%s' "$row" | cut -f11)"
dday="$(printf '%s\n' "$blocker $nextlev" | grep -oE 'D-[0-9]+' | head -1 || true)"

# resolve the submission folder: explicit --dir, else a staged _제출_* dir, else deliverables/, else campaign dir
campdir="$ROOT/$cdir"
if [ -z "$subdir" ]; then
  subdir="$(find "$campdir" -maxdepth 1 -type d -name '_제출_*' 2>/dev/null | head -1 || true)"
  [ -n "$subdir" ] || { [ -d "$campdir/deliverables" ] && subdir="$campdir/deliverables"; }
  [ -n "$subdir" ] || subdir="$campdir"
fi
[ -d "$subdir" ] || { echo "submission dir not found: $subdir" >&2; exit 1; }

pkgdir="$PH_HOME/EXIT/packages"; mkdir -p "$pkgdir"
[ -n "$out" ] || out="$pkgdir/${key}_submission_${DATE}.zip"
guide="$subdir/SUBMISSION_GUIDE.md"

# ---- build manifest (skip heavy/derived dirs so the zip stays emailable ≤25MB) ----
manifest="$(cd "$subdir" && find . -type f \
   ! -path '*/node_modules/*' ! -path '*/.git/*' ! -path '*/dist/*' ! -path '*/build/*' \
   ! -name 'SUBMISSION_GUIDE.md' -printf '%s\t%p\n' | sort -k2)"

# ---- auto-generate the founder guide ----
{
  echo "# 제출 가이드 — ${key}"
  echo
  echo "_생성: $(date '+%Y-%m-%d %H:%M KST')  ·  prizehunter package_submission_"
  echo
  echo "## 한눈에"
  echo "- 대회 키: **${key}**"
  [ -n "$dday" ] && echo "- 마감: **${dday}**"
  echo "- 블로커(=founder 할 일): ${blocker}"
  echo "- 다음 레버: ${nextlev}"
  echo
  echo "## founder 체크리스트 (제출 전 확인)"
  case "$key" in
    aic-usecase)
      echo "- [ ] AIC microsite 본인인증/login 및 개인정보·저작권·활용 동의 확인"
      echo "- [ ] 시즌/접수창이 현재 열려 있는지 확인"
      echo "- [ ] 분야 1개 선택: 권장 \`지역사회 문제해결 / 복약안전\`"
      echo "- [ ] 본문은 \`FINAL_PORTAL_TEXT.md\`를 사용하고, raw planning note는 업로드하지 않음"
      echo "- [ ] AI 도구 활용, 사람 검토, 의료안전 redaction, 개인정보 비사용을 고지"
      echo "- [ ] 진단·처방변경·복용중단 지시 문구가 없는지 최종 확인"
      ;;
    2026-create-the-future)
      echo "- [ ] Create the Future 공식 계정/login 및 Contest Rules 확인"
      echo "- [ ] \`ABSTRACT_500_WORDS.md\`가 500 words 이하인지 포털 붙여넣기 전 재확인"
      echo "- [ ] \`illustrations/\` 3개 PNG 중 공식 양식에 맞는 이미지 수만 선택"
      echo "- [ ] IP/originality warranty를 founder 본인이 확인"
      echo "- [ ] AI/tool 사용 고지가 필요한 입력란이 있으면 정직하게 기재"
      echo "- [ ] 의료기기/복약안전 표현이 처방·진단·복용변경 지시로 읽히지 않는지 최종 확인"
      ;;
    *)
      echo "- [ ] 개인 서식(참가신청서·서약서·개인정보 동의 등) **서명/날인**"
      echo "- [ ] 기획서 내용 최종 확인 (팀명·연락처 일치)"
      ;;
  esac
  case "$key" in
    wevity-busan-pubdata)
      echo "- [ ] 이메일 제출: 공고에 명시된 공식 접수처로 최종 HWP/PDF/증빙 zip 송부 (접수처 주소는 캠페인 RECON.md에서 확인)"
      ;;
    aic-usecase)
      echo "- [ ] AIC 공모전 마이크로 웹사이트에 블로그/이미지/텍스트 또는 1분 이내 숏폼으로 업로드"
      ;;
    2026-create-the-future)
      echo "- [ ] Create the Future 공식 entry form에 abstract/images 업로드"
      ;;
    *)
      echo "- [ ] 포털에 업로드 (대회 제출 페이지)"
      ;;
  esac
  echo "- [ ] 첨부(시제품/데이터/캡처) 누락 없는지 확인"
  echo "- [ ] 제출 완료 후 prizehunter에 '제출됨' 회신"
  echo
  echo "## 패키지 포함물 (manifest)"
  echo '```'
  printf '%s\n' "$manifest" | awk -F'\t' '{printf "  %8.1f KB  %s\n", $1/1024, $2}'
  echo '```'
  echo
  echo "## 주의"
  echo "- 이 패키지는 제출 자료 사본입니다. 외부 제출은 **founder 컨펌 후** 직접 진행합니다(안전게이트)."
  if [ "$package_mode" = "email-safe" ]; then
    echo "- 이메일 첨부용 zip은 Gmail 보안정책상 실행파일류(.js/.jar/.exe 등)를 제외합니다. **전체본(.js 포함)은 로컬 스테이징**에 있습니다."
  else
    echo "- 포털/Devpost 제출용 full zip입니다. 실행에 필요한 .js 등 웹 자산을 제외하지 않습니다."
  fi
  echo "- 원본 스테이징: \`$subdir\`"
} > "$guide"

# ---- zip ----
rm -f "$out"
zip_excludes=(-x '*/node_modules/*' -x '*/.git/*' -x '*/dist/*' -x '*/build/*')
if [ "$package_mode" = "email-safe" ]; then
  # Gmail 552-blocks attachments containing .js/.jar/.exe/... even inside zips.
  zip_excludes+=(
    -x '*.js' -x '*.jar' -x '*.exe' -x '*.bat' -x '*.cmd' -x '*.scr'
    -x '*.vbs' -x '*.vbe' -x '*.ps1' -x '*.com' -x '*.msi' -x '*.jse'
  )
fi
( cd "$subdir" && zip -q -r "$out" . "${zip_excludes[@]}" )
sz="$(du -h "$out" | cut -f1)"
szb="$(stat -c%s "$out")"

echo "key        : $key"
echo "submission : $subdir"
echo "guide      : $guide"
echo "zip        : $out"
echo "size       : $sz ($szb bytes)"
[ "$szb" -gt 26214400 ] && echo "WARN: >25MB — Gmail 첨부 한도 초과. notify_founder가 경로/링크 모드로 전환." || echo "OK: ≤25MB"
echo "mode       : $package_mode"
echo "files      : $(printf '%s\n' "$manifest" | grep -c . )"
# emit machine-readable line for notify_founder.sh
echo "PKG_OUT=$out"
echo "PKG_GUIDE=$guide"
echo "PKG_DDAY=$dday"
