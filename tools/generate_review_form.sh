#!/usr/bin/env bash
# generate_review_form.sh — creates a structured Founder feedback form for a campaign.
# Usage: bash generate_review_form.sh <campaign_key> [work_summary]
set -u
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"
KEY="${1:?need campaign key}"
SUMMARY="${2:-}" # optional work summary passed by caller

# Find campaign dir
CAMP_DIR=$(find "$PH_HOME/campaigns" -maxdepth 1 -type d -name "*${KEY}*" | head -1)
if [ -z "$CAMP_DIR" ]; then
  echo "ERROR: campaign dir not found for key=$KEY" >&2; exit 1
fi

FORM="$CAMP_DIR/FEEDBACK_REQUEST.md"
TS=$(date -u +%Y-%m-%d\ %H:%M\ UTC)

# Read worklog summary if no summary provided
if [ -z "$SUMMARY" ]; then
  SUMMARY=$(tail -20 "$CAMP_DIR/AGENT_WORKLOG.md" 2>/dev/null | grep -v "^#" | tr '\n' ' ' | cut -c1-300 || echo "작업 완료")
fi

cat > "$FORM" << FORMEOF
# 📋 Founder 리뷰 요청 — ${KEY}
생성: ${TS}

## 작업 내용 요약
${SUMMARY}

---
## Founder 평가 (아래 체크박스에 [x] 표시 + 주관식 작성)

### Q1. 전체 퀄리티 [택 1]
- [ ] A — 뛰어남, 제출 준비 완료
- [ ] B — 보통, 소폭 수정 후 제출 가능
- [ ] C — 부족함, 상당한 개선 필요
- [ ] D — 전면 재작성 필요

### Q2. 스토리라인 / 핵심 메시지 [택 1]
- [ ] A — 설득력 있고 명확함
- [ ] B — 방향은 맞으나 전달이 약함
- [ ] C — 재설계 필요
- [ ] N/A — 해당 없음 (코드/수치 작업 등)

### Q3. 데이터 · 분석 · 근거 [택 1]
- [ ] A — 충분하고 신뢰할 수 있음
- [ ] B — 더 보강 필요
- [ ] C — 약함 또는 재분석 필요
- [ ] N/A — 해당 없음

### Q4. 구체적으로 개선할 점 (주관식):
>

### Q5. 유지해야 할 좋은 점 (주관식):
>

### Q6. 전반적인 만족도 (1-10):
>

### Q7. 다음 우선순위 지시 (주관식, 선택):
>

---
*작성 후 Claude에게 "리뷰 완료, ${KEY}" 또는 해당 내용을 알려주세요.*
*또는 이 파일 내용을 그대로 Claude에게 공유해도 됩니다.*
FORMEOF

echo "FEEDBACK_REQUEST.md 생성: $FORM"
echo "Founder가 채워주면 prizehunter가 즉시 처리합니다."
