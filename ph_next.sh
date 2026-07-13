#!/usr/bin/env bash
# ph_next.sh — recommend the SINGLE next action (removes "which tool when?" burden),
# or --doctor to health-check every tool. Pure read; suggests, never acts.
set -u
PH_HOME="$(cd -- "$(dirname "$0")" && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true
T="$PH_HOME/tools"; REG="$PH_HOME/portfolio_registry.tsv"

if [ "${1:-}" = "--doctor" ]; then
  echo "== ph doctor — tool health =="
  bad=0
  for f in "$T"/*.sh "$PH_HOME/ph" "$PH_HOME/ph_next.sh"; do
    bash -n "$f" 2>/dev/null || { echo "  ❌ bash syntax: $(basename "$f")"; bad=$((bad+1)); }
  done
  for f in "$T"/*.py; do python3 -m py_compile "$f" 2>/dev/null || { echo "  ❌ py syntax: $(basename "$f")"; bad=$((bad+1)); }; done
  echo "  $([ $bad -eq 0 ] && echo '✅ all tools parse' || echo "$bad broken")"
  exit 0
fi

age_min() { [ -f "$1" ] && echo $(( ( $(date +%s) - $(stat -c %Y "$1") ) / 60 )) || echo 999999; }
campaign_dir_for() {
  awk -F'\t' -v key="$1" 'NR>1 && $1==key {print $2; exit}' "$REG" 2>/dev/null
}
has_gap_loop() {
  cdir="$(campaign_dir_for "$1")"
  [ -n "$cdir" ] && [ -f "$PH_HOME/../../$cdir/PRIZE_GAP_LOOP.md" ]
}
has_plan() {
  cdir="$(campaign_dir_for "$1")"
  [ -n "$cdir" ] && [ -f "$PH_HOME/../../$cdir/PLAN.md" ]
}
catalog="$PH_HOME/MASTER_CATALOG.md"; roi="$PH_HOME/ROI_REPORT.md"; qgate="$PH_HOME/QUALITY_GATE_REPORT.tsv"
if [ -f "$REG" ] && { [ ! -f "$qgate" ] || [ "$REG" -nt "$qgate" ]; }; then
  python3 "$T/quality_gate.py" >/dev/null 2>&1 || true
fi
active=$(awk -F'\t' 'NR>1&&$1!~"^#"&&$1!="key"&&$9=="active"{print $1}' "$REG" 2>/dev/null | paste -sd, -)
nactive=$(awk -F'\t' 'NR>1&&$1!~"^#"&&$1!="key"&&$9=="active"{n++}END{print n+0}' "$REG" 2>/dev/null)
fgates=$(awk -F'\t' 'NR>1&&$1!~"^#"&&$9=="blocked"&&$10~/FOUNDER/{print $1}' "$REG" 2>/dev/null | paste -sd, -)
running=$(tmux has-session -t "${PH_SESSION:-prizehunt}" 2>/dev/null && echo yes || echo no)
human_gate_re='FOUNDER:|ToS|final submit|final portal|login|account|spend|written confirmation|organizer|real operator/founder walkthrough|founder handles|founder-gate|founder 개인|빌드불가|미개시|추후공개|데이터 미공개|signup|가입|지갑|실 USDC|외부 제출|최종 제출|서명|날인'
agent_actionable_re='AGENT|agent-actionable|no-stake|Continue|Run full|benchmark exposure|trace capture|deterministic exploration|environment taxonomy|public baseline|local harness|cheap baseline|feature sets|neutralization|ensemble'
park_re='^(HOLD|WATCH|MONITOR|DROP|PARK)|\\bwatch weekly\\b|\\breactivate when\\b|official page contains 2026|not open|공고 미발표'

echo "== ph next — recommended action =="
if [ "$(age_min "$catalog")" -gt 10080 ]; then
  echo "→ ph discover      (no/stale catalog — pull all platforms first)"
elif [ ! -f "$roi" ] || [ "$(age_min "$roi")" -gt 1440 ]; then
  echo "→ ph money         (catalog ready; ROI-rank the money — \"돈 되는 것만\")"
elif [ -f "$qgate" ]; then
  qrow="$(awk -F'\t' 'NR>1 && $3=="active" && $8 !~ /^LOW/ {print; exit}' "$qgate" 2>/dev/null)"
  if [ -n "$qrow" ]; then
    qkey="$(printf '%s' "$qrow" | cut -f1)"
    qwin="$(printf '%s' "$qrow" | cut -f7)"
    qnext="$(printf '%s' "$qrow" | cut -f10)"
    if printf '%s\n' "$qnext" | grep -Eiq "$human_gate_re"; then
      echo "⛔ waiting gate → $qkey   (highest active quality/EV gate, win≈${qwin}%)"
      echo "   needs: $qnext"
      arow="$(awk -F'\t' -v human="$human_gate_re" -v park="$park_re" '
        NR>1 && $3 ~ /^(active|scaffold|recon)$/ && $8 !~ /^LOW/ {
          next_gate=$10
          if (next_gate ~ park) next
          if (next_gate ~ agent) {print; exit}
          if (next_gate !~ human) {print; exit}
        }' agent="$agent_actionable_re" "$qgate" 2>/dev/null)"
      if [ -n "$arow" ]; then
        akey="$(printf '%s' "$arow" | cut -f1)"
        astatus="$(printf '%s' "$arow" | cut -f3)"
        anext="$(printf '%s' "$arow" | cut -f10)"
        if [ "$astatus" = "active" ]; then
          echo "→ ph run $akey --exec   (agent-actionable while waiting)"
        elif has_plan "$akey"; then
          echo "→ ph run $akey --exec   (plan exists; start execution loop)"
        elif has_gap_loop "$akey"; then
          echo "→ ph plan $akey \"$akey\"   (gap loop exists; move to campaign plan)"
        else
          echo "→ ph gap $akey \"$akey\"   (agent-actionable while waiting)"
        fi
        echo "   why: $anext"
      else
        echo "→ ph pool              (no non-human active gate; promote the next EV candidate)"
      fi
    else
      echo "→ ph quality → $qkey   (highest active quality/EV gate, win≈${qwin}%)"
      echo "   next: $qnext"
    fi
  elif [ "$nactive" -eq 0 ]; then
    echo "→ ph plan <key> \"<name>\"   (no committed campaigns; pick a GO row from ph money / catalog)"
  elif [ "$running" = "no" ]; then
    echo "→ ph parallel $active   (campaigns committed but no workers running — launch them)"
  else
    echo "→ ph status / drive workers   ($nactive active, workers running)"
  fi
elif [ "$nactive" -eq 0 ]; then
  echo "→ ph plan <key> \"<name>\"   (no committed campaigns; pick a GO row from ph money / catalog)"
elif [ "$running" = "no" ]; then
  echo "→ ph parallel $active   (campaigns committed but no workers running — launch them)"
else
  echo "→ ph status / drive workers   ($nactive active, workers running)"
fi
[ -n "$fgates" ] && echo "⛔ delegated-gated: $fgates  — clear only through SUBMISSION_AUTOMATION.md standing-delegation receipts; keep going on the rest"
echo "   (full surface: ph status · ph help)"
