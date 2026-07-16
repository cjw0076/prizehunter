#!/usr/bin/env bash
# ph — the ONE front door for agents. Wraps ~39 internal tools behind a small,
# consistent verb set so an agent learns 10 verbs, not 39 scripts. Every verb
# prints what it did + the suggested next step. `ph next` = "what do I do now".
set -u
PH_HOME="$(cd -- "$(dirname "$0")" && pwd)"; . "$PH_HOME/config.sh" 2>/dev/null || true
T="$PH_HOME/tools"
v="${1:-help}"; shift || true

case "$v" in
  help|-h|--help)
    cat <<EOF
ph — Prize Hunter control surface (run any verb; each tells you the next step)

  ph status              one dashboard: board + top money + who-drives-what
  ph next                ← recommends the single next action (start here if unsure)
  ph discover            refresh the master catalog (all platforms, KR + intl)
  ph money               ROI-rank "돈 되는 것만"  (verify prize)
  ph plan <key> "<name>" decompose a competition into a campaign plan
  ph run <key> [--exec]  drive one competition (dry-run unless --exec)
  ph parallel <k1,k2,..> open tmux workers (CLI agents in parallel)
  ph dispatch <agent> "<task>"   hand work to another agent (route/escalate)
  ph route "<task>"       token-saving model route before dispatch
  ph collab <key> "<name>"       Codex creative brief → Claude main build loop
  ph discuss <cmd> [args]         shared agent opinion workspace (init/post/list/show/decision)
  ph learn --summary ...          record a failure/blocker as reusable learning
  ph recall "<task>"     pull accumulated MemoryOS expertise for a domain
  ph visual              Codex visual QA: hero assets + per-competition media
  ph video [key|--all]   Higgsfield/Seedance queue: image board → cheap vibe → final
  ph pool                build next cross-domain competition pool
  ph materialize [N]     create campaign folders/plans/creative briefs from pool
  ph judge               strict Codex judge scoreboard: progress/completeness/win chance
  ph quality             quality/EV gate: submission readiness vs judge quality vs win chance
  ph novelty             auxiliary goal: fresh value proposition + stale-approach risk
  ph submitted [--check] submitted/active board: links, check methods, evidence
  ph confirm [--init|--check|--path] login/submit confirmation system: runbook + private vault checks
  ph chase               post-submission/rank-1 chase board
  ph automation          submission automation matrix: API/CLI/Playwright/gates
  ph gates               founder/auth gate dashboard: what the user must clear
  ph profile             draft operator/user preference model from safe local signals
  ph agents              usage mix vs target share for Claude/Codex/Gemini/etc.
  ph api get <endpoint>  call prizehunter-web REST reads, e.g. board
  ph api post <endpoint> '{...}'  call REST writes with PH_API_KEY
  ph team ...            team mode: init/onboard/checkin/review/idea/message
  ph complete [key]      completeness gate: package evidence, placeholders, founder gates
  ph strategy            lane-specific win thesis, required proof, kill rule, agent route
  ph gap <key> "<name>"  mine judge intent, our gaps, and 120% backlog
  ph tick                record + refresh + flywheel deposit (the heartbeat)
  ph radar               deadline radar: D-day board + 마감경과 자동 아카이브 리포트
  ph pnl                 P&L: registry→prize ledger 동기화 + 비용(EXIT/COSTS.tsv) 합산 요약
  ph settle [close <key> …]  '끝난 후' 정산: 결과 radar / 결과확정→포스트모템→포트폴리오 (playbook/POSTERIOR.md)
  ph results             공개 페이지로 결과 자동 확인(Devpost 리본/공지) → settle 제안
  ph portfolio           대회 성과 인덱스(PORTFOLIO_INDEX.md) 재생성 + 표시
  ph control             boot the autonomous control plane (= "prizehunter")
  ph feedback <key> "<msg>"     log founder dissatisfaction → worker task queue
  ph requests                   show pending founder requests (prizehunter reads this on boot)
  ph review <key> [summary]     generate structured Founder feedback form (객관식+주관식) for a campaign
  ph parse-review <key>         parse completed feedback form → revision task in founder_requests.md
  ph capabilities [filter]      check which tools/MCPs are available vs missing for active campaigns
  ph find-tool "<need>"         search MCP marketplaces for a specific capability
  ph creative "<topic>" [key]   anti-AI-default creative divergence: 5 wild framings before building
  ph autonomy             self-check: what runs unattended vs what to fill
  ph onboard [gate]       ask for ONLY the credential a gate needs, then resume
  ph session --site <s>   log in once → agent extracts API token from browser → vault
  ph vault KEY VALUE      store one supplied credential (gitignored)
  ph ontology             build the approach/context ontology from finished competitions
  ph inherit <key|-m M>   inherit+evolve approaches for a new competition (from ontology)
  ph goal [key|--board]   per-competition verdict: PUSH/CEILING?/AT_#1 until rank #1
  ph calibrate           predicted-vs-actual → triage self-correction (getting smarter)
  ph council "<q>"       heterogeneous 2nd opinion (your codex/gemini/nim/ollama)
  ph issue "<title>"     file a GitHub issue (agent-native self-reporting)
  ph qa                  release gate: fresh-clone smoke + parse + secrets (run before push)
  ph doctor              health-check the tools (find broken ones)
EOF
    ;;
  status)   bash "$T/strategist_brief.sh" >/dev/null 2>&1; python3 "$T/quality_gate.py" >/dev/null 2>&1
            sed -n '1,40p' "$PH_HOME/STRATEGIST_BRIEF.md" 2>/dev/null
            echo
            echo "## Quality Gate (progress ≠ win probability)"
            sed -n '1,24p' "$PH_HOME/QUALITY_GATE_REPORT.md" 2>/dev/null | sed -n '/| win% /,$p'
            echo; echo "next → ph next" ;;
  next)     bash "$PH_HOME/ph_next.sh" 2>/dev/null || echo "see: ph status" ;;
  discover) bash "$T/catalog.sh" "$@"; echo "next → ph money" ;;
  money)    python3 "$T/prize_roi.py" --fetch "$@"; echo "next → ph plan <key> \"<name>\"  (pick a GO row)" ;;
  plan)     k="${1:?ph plan <key> \"<name>\"}"; n="${2:-$k}"; python3 "$T/plan_campaign.py" --key "$k" --name "$n" "${@:3}"; echo "next → ph run $k" ;;
  run)      k="${1:?ph run <key> [--exec]}"; shift || true
            ex=""; [ "${1:-}" = "--exec" ] && ex="--execute"
            bash "$T/run_campaign.sh" --key "$k" $ex; echo "next → ph parallel (add more) or ph run $k --exec" ;;
  parallel) bash "$T/run_parallel.sh" --keys "${1:?ph parallel <k1,k2,..>}" "${@:2}"; echo "next → ph status" ;;
  dispatch) a="${1:?ph dispatch <agent> \"<task>\"}"; AGENT="${AGENT:-ph}" bash "$T/agent_dispatch.sh" --to "$a" --task "${2:?need task}" "${@:3}" ;;
  route)    python3 "$T/model_router.py" "$@" ;;
  collab)   k="${1:?ph collab <key> \"<name>\"}"; n="${2:?need name}"; shift 2
            python3 "$T/collab_workloop.py" --key "$k" --name "$n" "$@"; echo "next → Codex fill campaigns/$k/CREATIVE_BRIEF.md, then ph collab $k \"$n\" --dispatch all --execute" ;;
  discuss)  if [ "$#" -eq 0 ]; then python3 "$T/agent_workspace.py" list; else python3 "$T/agent_workspace.py" "$@"; fi ;;
  learn)    bash "$T/record_failure_learning.sh" "$@"; echo "next → change the approach/provider/validation before retrying" ;;
  recall)   bash "$T/memoryos_bridge.sh" recall --task "${1:?ph recall \"<task>\"}" ;;
  visual)   bash "$T/visual_confirm.sh"; echo "next → ph tick" ;;
  video)    python3 "$T/video_pipeline.py" "$@" || exit $?
            sed -n '1,160p' "$PH_HOME/VIDEO_PIPELINE_REPORT.md" 2>/dev/null
            echo "next → fill video_assets/source_image_manifest.tsv, then run low-cost Seedance vibe checks" ;;
  pool)     python3 "$T/build_next_pool.py"; echo "next → ph gap <key> \"<name>\" then ph collab/plan" ;;
  materialize)
            n="${1:-50}"
            python3 "$T/materialize_next_pool.py" --limit "$n" --min-score 50 --execute-tools
            echo "next → Codex fills creative briefs for codex_creative_director rows; ph collab <key> \"<name>\" --dispatch all --execute" ;;
  judge)    python3 "$T/judge_scoreboard.py"; python3 "$T/quality_gate.py"; echo "next → act on the lowest-score P0 quality gate or founder gate" ;;
  quality)  python3 "$T/quality_gate.py" || exit $?; echo "next → fix the first hard-disqualifier before polishing" ;;
  novelty)  python3 "$T/novelty_value_board.py" || exit $?; sed -n '1,180p' "$PH_HOME/NOVELTY_VALUE_BOARD.md"; echo "next → act on the highest stale-risk row or update the campaign thesis" ;;
  submitted) python3 "$T/submission_board.py" "$@" || exit $?; sed -n '1,150p' "$PH_HOME/SUBMISSION_BOARD.md"; echo "next → ph next" ;;
  confirm)   python3 "$T/submission_confirm.py" "$@" || exit $?; echo "next → fill private vault locally, then ph confirm --check && ph submitted --check" ;;
  chase)     python3 "$T/post_submission_chase.py" || exit $?; echo "next → act on first rank1_chase or judge_satisfaction_iteration row" ;;
  automation) python3 "$T/submission_automation_matrix.py" || exit $?; sed -n '1,180p' "$PH_HOME/SUBMISSION_AUTOMATION_MATRIX.md"; echo "next → ph submitted --check" ;;
  gates)    python3 "$T/founder_auth_dashboard.py" || exit $?; sed -n '1,180p' "$PH_HOME/FOUNDER_AUTH_DASHBOARD.md"; echo "next → clear one gate, then ph submitted --check && ph tick" ;;
  profile)  python3 "$T/operator_profile.py" "$@"; sed -n '1,180p' "$PH_HOME/OPERATOR_PROFILE_DRAFT.md" ;;
  agents)   python3 "$T/agent_usage.py" "$@"; echo "next → adjust AGENT_USAGE_POLICY.tsv or route with ph dispatch <agent> \"<task>\"" ;;
  api)      python3 "$T/ph_api.py" "$@" ;;
  team)     if [ $# -eq 0 ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
              python3 "$T/team_ops.py"
            elif [ "${1#--}" != "$1" ]; then
              python3 "$T/team_ops.py" message "$@"
            else
              python3 "$T/team_ops.py" "$@"
            fi ;;
  complete) if [ $# -gt 0 ]; then python3 "$T/completeness_review.py" --key "$1"; else python3 "$T/completeness_review.py"; fi
            sed -n '1,80p' "$PH_HOME/COMPLETENESS_REVIEW.md"
            echo "next → ph quality" ;;
  strategy) python3 "$T/quality_gate.py" >/dev/null
            sed -n '1,260p' "$PH_HOME/STRATEGY_PLAYBOOK_BY_LANE.md"
            echo "next → ph quality" ;;
  gap)      k="${1:?ph gap <key> \"<name>\"}"; n="${2:?need name}"; shift 2
            python3 "$T/prize_gap_loop.py" --key "$k" --name "$n" "$@"; echo "next → ph collab $k \"$n\" or ph plan $k \"$n\"" ;;
  tick)     bash "$T/portfolio_tick.sh" ;;
  radar)    python3 "$T/deadline_watchdog.py" --report; echo "next → clear the nearest D-day founder gate, or ph tick" ;;
  pnl)      python3 "$T/pnl_sync.py"; echo; sed -n '1,40p' "$PH_HOME/EXIT/PNL_SUMMARY.md" 2>/dev/null
            echo "next → fill won_amount/placement evidence in EXIT/PRIZE_LEDGER.tsv; record spend in EXIT/COSTS.tsv" ;;
  settle)   if [ $# -eq 0 ]; then python3 "$T/settle.py" watch; echo; sed -n '1,40p' "$PH_HOME/RESULTS_RADAR.md" 2>/dev/null
            else python3 "$T/settle.py" "$@"; fi
            echo "next → ph settle close <key> --outcome won|placed|lost|no_award|lapsed --evidence \"…\" → 포스트모템 TBD 채우기" ;;
  results)  python3 "$T/result_check.py" --force; echo; sed -n '1,40p' "$PH_HOME/RESULT_CHECK.md" 2>/dev/null
            echo "next → 제안 evidence 링크 확인 후 ph settle close … 로 확정" ;;
  portfolio) python3 "$T/build_portfolio.py"; echo; sed -n '1,50p' "$PH_HOME/PORTFOLIO_INDEX.md" 2>/dev/null
            echo "next → CASE_STUDY/POSTMORTEM TBD 채우기; 외부 게시(jw-portfolio/SNS)는 founder gate" ;;
  control)  bash "$T/prizehunter.sh" ;;
  review) k="${1:?ph review <key>}"; shift; bash "$T/generate_review_form.sh" "$k" "${*:-}"
          echo "next → share campaigns/*${k}*/FEEDBACK_REQUEST.md with Founder to fill in, then: ph parse-review $k" ;;
  parse-review) k="${1:?ph parse-review <key>}"; python3 "$T/parse_review_feedback.py" "$k"
          echo "next → ph requests  (shows revision tasks derived from feedback)" ;;
  capabilities) bash "$T/check_capabilities.sh" "${1:-}"
          echo "next → install missing tools, then re-run ph capabilities to confirm" ;;
  creative) topic="${1:?ph creative \"<topic>\"}"; key="${2:-}"; bash "$T/creative_diverge.sh" "$topic" "$key"
          echo "next → pick the most surprising angle, then: ph plan <key> \"<name>\"" ;;
  find-tool) need="${1:?ph find-tool \"<need>\"}"; shift
          echo "Searching Smithery for: $need"
          npx --yes @smithery/cli search "$need" 2>/dev/null || true
          echo ""
          echo "Also check:"
          echo "  • Smithery:  https://smithery.ai/search?q=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$need'))" 2>/dev/null || echo "$need")"
          echo "  • mcp.so:    https://mcp.so/search?q=$need"
          echo "  • glama:     https://glama.ai/mcp/servers?search=$need"
          echo "  • PulseMCP:  https://www.pulsemcp.com/servers?search=$need"
          echo "next → npx @smithery/cli install <server-name>  OR  add to ~/.claude.json" ;;
  feedback) key="${1:?ph feedback <key> \"<msg>\"}"; msg="${2:?need message}"; shift 2
            ts=$(date -u +%Y-%m-%d)
            reqf="$PH_HOME/founder_requests.md"
            printf '\n## [pending] %s — %s\n\n**Founder 피드백**: "%s"\n\n**Worker 작업**: [ ] TBD\n\n**마감**: TBD\n' "$key" "$ts" "$msg" >> "$reqf"
            echo "Logged founder request for $key. View with: ph requests"
            echo "next → review $reqf, add Worker 작업, then run prizehunter to process" ;;
  requests) grep -E "^\## \[(pending|in_progress)\]" "$PH_HOME/founder_requests.md" 2>/dev/null || echo "No pending founder requests."
            echo; echo "Full log: $PH_HOME/founder_requests.md"
            echo "next → pick the first [pending] item and execute as highest-priority work" ;;
  autonomy) bash "$T/ph_gates.sh" ;;
  onboard)  bash "$T/onboard.sh" "$@" ;;
  session)  python3 "$T/session_capture.py" "$@" ;;
  vault)    bash "$T/vault_set.sh" "$@" ;;
  calibrate) python3 "$T/calibration.py" "$@"; sed -n "1,30p" "$PH_HOME/CALIBRATION_REPORT.md" 2>/dev/null
            echo "next → feed the triage nudge into triage_competition.py priors" ;;
  council)  bash "$T/council.sh" "$@"; echo "next → synthesize the independent reads, verify, then decide" ;;
  issue)    t="${1:?ph issue \"<title>\" [body]}"; b="${2:-}"; bash "$T/report_issue.sh" --title "$t" --body "$b"
            echo "next → maintainer triages; set PH_ISSUE_REPO=owner/name to route" ;;
  doctor)   bash "$PH_HOME/ph_next.sh" --doctor 2>/dev/null || { echo "checking tools..."; for f in "$T"/*.sh; do bash -n "$f" 2>/dev/null || echo "  ❌ syntax: $(basename "$f")"; done; echo "done"; } ;;
  qa)       bash "$T/qa_harness.sh" "$@" ;;
  *) echo "unknown verb: $v"; exec "$0" help ;;
esac
