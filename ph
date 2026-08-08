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
  ph auto                자율드라이브 대회 보드 (게이트0 프로그래매틱: CrunchDAO/Kaggle/DrivenData/AIcrowd)
  ph scrape <url> [args] 범용 SPA/anti-bot 스크래퍼 (Scrapling; 로그인·게이트 없이 읽기)
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
  ph kevin [--target P]  sync prizehunter state into kevin8738/Dacon dashboard
  ph team ...            team mode: init/onboard/checkin/review/idea/message
  ph complete [key]      completeness gate: package evidence, placeholders, founder gates
  ph strategy            lane-specific win thesis, required proof, kill rule, agent route
  ph gap <key> "<name>"  mine judge intent, our gaps, and 120% backlog
  ph goal [--board|--key K]   goal loop: drive verdicts (PUSH/REFUTE/…) per competition
  ph name <key> [run]         NAMING ORGAN — escape a stuck framing by NAMING it (data 매몰 방지): name the rut → heterogeneous voices name the residual → witness gate → orthogonal frame
  ph selfcheck            proprioception: is the system's OWN state (senses·loops) provably alive? (fail-closed)
  ph tick                record + refresh + flywheel deposit (the heartbeat)
  ph sync                push board state to the hosted control-plane (Supabase → web dashboard)
  ph sandbox -- CMD…     run agent-generated code in the container sandbox (no net, non-root)
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
  ph doctor              health-check the tools (find broken ones)
  ph autonomy             self-check: what runs unattended vs what to fill
  ph onboard [gate]       ask for ONLY the credential a gate needs, then resume
  ph session --site <s>   log in once → agent extracts API token from browser → vault
  ph browser <open|click|accept|form> …   handle a WEB gate directly (rules accept, form) — not an operator gate
  ph vault KEY VALUE      store one supplied credential (gitignored)
  ph calibrate           predicted-vs-actual → triage self-correction (getting smarter)
  ph council "<q>"       heterogeneous 2nd opinion (your codex/gemini/nim/ollama)
  ph issue "<title>"     file a GitHub issue (agent-native self-reporting)
  ph qa                  release gate: fresh-clone smoke + parse + secrets (run before push)
  ph qa-team [--scope S] standing QA team: role-specialized reviewers (heterogeneous models)
  ph rnd [board|propose|harvest|add|result|select]  evolutionary R&D on the system itself
EOF
        echo ""
    echo "  ── 2026-07-26 진화 층 ──"
    echo "  ph steer \"<한 줄>\" | <key> \"<한 줄>\" | list | clear <scope>   ★CENTAUR: founder 직관 5%를 드라이브 브리프 최상위 권위로 즉시 주입"
    echo "  ph consult ask|panel <key> \"<질문>\" | diverge <key> | claims <key> | push <key> \"<반박>\" | adopt <key>"
    echo "                           ★이종 자문: ask=agy(Gemini 3.1 Pro high) · panel=agy+council(perplexity/deepseek/claude.ai)"
    echo "                           → diverge(합의보다 불일치가 정보) → claims(수치·코드 추출+대수붕괴 검출) → push(반박 되돌리기) → adopt(검증 통과분만 브리프)"
    echo "  ph agent roster|ask <k> <role> \"<p>\"|attack <k> \"<claim>\"|sessions   ★지속세션 에이전트(claude/agy/codex) + 이종 적대검증"
    echo "  ph lb [--sync] | ph breaker check <ledger> | ph contract selftest   ★목표 신선도 · 정체 감지 · 출력계약(자율성 3가드레일)"
    echo "  ph view <key>            ★기하 렌더: train↔test 분포·엔티티 수·스키마 괴리 그림(VIEW/index.html) + 기계용 숫자(VIEW/FINDINGS.md)"
    echo "  ph resonate ask|commit|outcome|status   ★SPINE 공진루프: 내 답을 이종substrate가 공격 → 외부액션 커밋 → 결과기록 → 다음 질문"
    echo "  ph audit                 목표 감사 (자기참조·산문 rank1·stale ceiling·나쁜 dir) — 드라이브 전에 항상"
    echo "  ph frame check|make <k>  진입프레임 (검증된 목표·harness신뢰·3+프레이밍·PRIOR태깅·판정어 금지)"
    echo "  ph gap system | comp <k> 구조적 괴리 사냥 (train↔test·CV↔LB·public↔private·오차예산 / 기계 자기감사)"
    echo "  ph evolve [--execute]    goal_loop 판정→arm 통합 드라이브 (PUSH/REFUTE/HARD_PIVOT/JUDGED)"
    echo "  ph meta allocate|priors|variants|exhausted <tt>   프로세스 복리 (어디에·어떤 렌즈·어떤 프롬프트변형)"
    echo "  ph brief <k> <tt>        변형가능 프롬프트 조립 (BRIEF_BANK.md — 헤드가 계속 변형)"
    echo "  ph judge120 <k> <dir>    제출형 120% 적대심사 게이트 (통과만 founder 컨펌)"
    echo "  ph cockpit [--port N]    daemon + 웹 코킷 (자기푸시 루프·컨펌큐·멀티테넌트)"
    ;;
  status)   bash "$T/strategist_brief.sh" >/dev/null 2>&1; python3 "$T/quality_gate.py" >/dev/null 2>&1
            sed -n '1,40p' "$PH_HOME/STRATEGIST_BRIEF.md" 2>/dev/null
            echo
            echo "## Quality Gate (progress ≠ win probability)"
            sed -n '1,24p' "$PH_HOME/QUALITY_GATE_REPORT.md" 2>/dev/null | sed -n '/| win% /,$p'
            echo; echo "next → ph next" ;;
  next)     bash "$PH_HOME/ph_next.sh" 2>/dev/null || echo "see: ph status" ;;
  # --- 2026-07-26 layer: entry frame · target audit · gap hunting · unified evolution · mutable briefs ---
  consult)  bash "$T/consult.sh" "$@" ;;
  agent)    bash "$T/session_agent.sh" "$@" ;;                                      # ★지속 세션 에이전트: roster/ask/attack/sessions (claude·agy·codex 세션 유지 + 이종 적대검증)
  contract) python3 "$T/contract.py" "$@" ;;                                        # ★하네스 계약 강제: 읽을 수 없는 출력은 DATAERR(65)로 즉시 실패
  breaker)  python3 "$T/breaker.py" "$@" ;;                                          # ★프레이밍 서킷브레이커: K회 정체 → 직교 재프레이밍 강제
  lb)       python3 "$T/lb_sensor.py" "$@" ;;                                        # ★리더보드 센서(+provenance 스탬프, cron 30분)                                            # ★이종 자문(agy/Gemini 3.1 Pro high) + 반박검증: ask→claims→push→adopt
  steer)    bash "$T/steer.sh" "$@" ;;                                              # ★CENTAUR: founder의 한 줄 지시를 즉시 드라이브 브리프 최상위 권위로 주입
  view)     python3 "$T/gap_view.py" "$@" ;;                                        # ★기하 렌더: train↔test 분포/엔티티수/스키마 괴리를 사람이 보는 그림 + 기계용 숫자
  smoke)    bash "$T/smoke.sh" "$@" ;;                                              # ★fresh-install 스모크: 남이 clone해도 부팅되는지 (배포 선행조건)
  preflight) bash "$T/preflight.sh" "$@" ;;                                         # ★제출 전 규정 체크리스트 + I CONFIRM 기록(지문 바인딩) — 실격 사고의 가장 값싼 방지책
  watch)    bash "$T/watch.sh" "$@" ;;                                              # ★감시 스크린: 워커 생사·대회 이동·자원·ideation 폭·게이트·doctor
  transfer) bash "$T/transfer_gate.sh" "$@" ;;                                      # ★전이 게이트: 검증한 것==제출한 것인가 + 로컬이득이 전이 하한선을 넘나
  resonate) bash "$T/resonate.sh" "$@" ;;                                           # ★SPINE: 재귀적 공진 루프(자기심문×이종substrate, 외부액션 게이트)
  audit)    python3 "$T/audit_targets.py" "$@" ;;                                  # 목표 감사(자기참조·산문·stale·나쁜dir)
  frame)    a="${1:-check}"; bash "$T/open_frame.sh" "$a" "${@:2}" ;;               # 진입프레임 검사/열기(판정어 금지·3+프레이밍)
  gap)      a="${1:-system}"
            case "$a" in
              comp|system) bash "$T/gap_hunt.sh" "$a" "${@:2}" ;;   # 구조적 괴리 사냥(대회 | system 자기감사)
              *) k="$a"; n="${2:?ph gap <key> \"<name>\"}"; shift 2
                 python3 "$T/prize_gap_loop.py" --key "$k" --name "$n" "$@"; echo "next → ph collab $k \"$n\" or ph plan $k \"$n\"" ;;
            esac ;;
  evolve)   bash "$T/evolve.sh" "$@" ;;                                             # goal_loop 판정→실행arm 통합 드라이브
  brief)    bash "$T/brief_render.sh" "$@" ;;                                       # 변형가능 프롬프트 조립(BRIEF_BANK.md)
  meta)     bash "$T/meta_learn.sh" "$@" ;;                                         # 프로세스 복리(렌즈/변형 랭킹·EV할당·소진판정)
  judge120) bash "$T/judge120.sh" "$@" ;;                                           # 제출형 120% 적대심사 게이트
  cockpit)  python3 "$T/prizehunterd.py" "$@" ;;                                    # daemon+웹코킷(자기푸시·컨펌큐·멀티테넌트)

  discover) bash "$T/catalog.sh" "$@"; echo "next → ph money" ;;
  money)    python3 "$T/prize_roi.py" --fetch "$@"; echo "next → ph plan <key> \"<name>\"  (pick a GO row)" ;;
  auto|autonomous)  cat "$PH_HOME/AUTONOMOUS_BOARD.md" 2>/dev/null || echo "no AUTONOMOUS_BOARD.md"; echo "next → 등록된 T1 드라이브 or programmatic_sources.tsv 스윕" ;;
  scrape)   "$T/scrape.py" "$@" ;;   # 범용 SPA/anti-bot 스크래퍼 (Scrapling); 사용법 tools/SCRAPE_TOOL.md
  plan)     k="${1:?ph plan <key> \"<name>\"}"; n="${2:-$k}"; python3 "$T/plan_campaign.py" --key "$k" --name "$n" "${@:3}"; echo "next → ph run $k" ;;
  run)      k="${1:?ph run <key> [--exec]}"; shift || true
            ex=""; [ "${1:-}" = "--exec" ] && ex="--execute"
            bash "$T/run_campaign.sh" --key "$k" $ex; rc=$?
            echo "next → ph parallel (add more) or ph run $k --exec"; exit $rc ;;
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
  kevin)    python3 "$T/quality_gate.py" >/dev/null
            python3 "$T/submission_board.py" >/dev/null
            python3 "$T/founder_auth_dashboard.py" >/dev/null
            python3 "$T/export_kevin_dashboard.py" "$@"
            echo "next → in the Kevin dashboard repo: node scripts/build_dashboard.js && git diff" ;;
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
  # doctor = mechanical self-diagnosis (doctor.sh: unsatisfiable gates, key fragmentation, orphan state,
  # scale mixing, cost leak, dead gate, disk) THEN the older per-tool health scan. Until now `ph doctor`
  # ran only the latter, so the gate-integrity classes were reachable only via `ph watch`/`ph next` —
  # the documented health verb was blind to the checks written to catch our most expensive defects.
  doctor)   bash "$T/doctor.sh" "$@"; rc=$?
            echo; bash "$PH_HOME/ph_next.sh" --doctor 2>/dev/null || { echo "checking tools..."; for f in "$T"/*.sh; do bash -n "$f" 2>/dev/null || echo "  ❌ syntax: $(basename "$f")"; done; echo "done"; }
            exit $rc ;;
  track)    bash "$T/trajectory.sh" "$@" ;;
  scout)    PATH="$HOME/.local/bin:$PATH" python3 "$T/scout.py" "$@"; echo "next → verify + add high-EV finds to DEEP_POOL.md, enter the best" ;;
  board)    bash "$T/drive_board.sh" "$@" ;;
  kernel)   bash "$T/kernel_submit.sh" "$@" ;;
  autonomy) bash "$T/ph_gates.sh" ;;
  onboard)  bash "$T/onboard.sh" "$@" ;;
  session)  python3 "$T/session_capture.py" "$@" ;;
  vault)    bash "$T/vault_set.sh" "$@" ;;
  calibrate) python3 "$T/calibration.py" "$@"; sed -n "1,30p" "$PH_HOME/CALIBRATION_REPORT.md" 2>/dev/null
            echo "next → feed the triage nudge into triage_competition.py priors" ;;
  council)  bash "$T/council.sh" "$@"; echo "next → synthesize the independent reads, verify, then decide" ;;
  issue)    t="${1:?ph issue \"<title>\" [body]}"; b="${2:-}"; bash "$T/report_issue.sh" --title "$t" --body "$b"
            echo "next → maintainer triages; set PH_ISSUE_REPO=owner/name to route" ;;
  qa)       bash "$T/qa_harness.sh" "$@" ;;
  qa-team)  bash "$T/qa_team.sh" "$@" ;;
  rnd)      python3 "$T/rnd_loop.py" "$@" ;;
  browser)  python3 "$T/browser_gate.py" "$@" ;;
  goal)     python3 "$T/goal_loop.py" "$@" ;;
  sync)     python3 "$T/dashboard_sync.py" "$@" ;;
  name)     k="${1:?ph name <key> [propose|judge|frame|run|log] (default run)}"; sub="${2:-run}"; shift $(( $#>=2 ? 2 : 1 ))
            bash "$T/name_organ.sh" "$sub" "$k" "$@" ;;   # 명명 조직: 갇힌 프레임에 이름→잔차 명명(codex/agy/local)→witness→직교 프레임
  sandbox)  bash "$T/sandbox_run.sh" "$@" ;;
  selfcheck) python3 "$T/proprioception.py" "$@" ;;   # 자기상태 감각(레지스트리·대시보드·eval·loop·gate) fail-closed 판정
  *) echo "unknown verb: $v" >&2; "$0" help >&2; exit 2 ;;
esac
