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
  ph kevin [--target P]  sync prizehunter state into kevin8738/Dacon dashboard
  ph team ...            team mode: init/onboard/checkin/review/idea/message
  ph complete [key]      completeness gate: package evidence, placeholders, founder gates
  ph strategy            lane-specific win thesis, required proof, kill rule, agent route
  ph gap <key> "<name>"  mine judge intent, our gaps, and 120% backlog
  ph tick                record + refresh + flywheel deposit (the heartbeat)
  ph control             boot the autonomous control plane (= "prizehunter")
  ph feedback <key> "<msg>"     log founder dissatisfaction → worker task queue
  ph requests                   show pending founder requests (prizehunter reads this on boot)
  ph review <key> [summary]     generate structured Founder feedback form (객관식+주관식) for a campaign
  ph parse-review <key>         parse completed feedback form → revision task in founder_requests.md
  ph capabilities [filter]      check which tools/MCPs are available vs missing for active campaigns
  ph find-tool "<need>"         search MCP marketplaces for a specific capability
  ph creative "<topic>" [key]   anti-AI-default creative divergence: 5 wild framings before building
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
  pool)     python3 "$T/build_next_pool.py"; echo "next → ph gap <key> \"<name>\" then ph collab/plan" ;;
  materialize)
            n="${1:-50}"
            python3 "$T/materialize_next_pool.py" --limit "$n" --min-score 50 --execute-tools
            echo "next → Codex fills creative briefs for codex_creative_director rows; ph collab <key> \"<name>\" --dispatch all --execute" ;;
  judge)    python3 "$T/judge_scoreboard.py"; python3 "$T/quality_gate.py"; echo "next → act on the lowest-score P0 quality gate or founder gate" ;;
  quality)  python3 "$T/quality_gate.py"; echo "next → fix the first hard-disqualifier before polishing" ;;
  novelty)  python3 "$T/novelty_value_board.py"; sed -n '1,180p' "$PH_HOME/NOVELTY_VALUE_BOARD.md"; echo "next → act on the highest stale-risk row or update the campaign thesis" ;;
  submitted) python3 "$T/submission_board.py" "$@"; sed -n '1,150p' "$PH_HOME/SUBMISSION_BOARD.md"; echo "next → ph next" ;;
  confirm)   python3 "$T/submission_confirm.py" "$@"; echo "next → fill private vault locally, then ph confirm --check && ph submitted --check" ;;
  chase)     python3 "$T/post_submission_chase.py"; echo "next → act on first rank1_chase or judge_satisfaction_iteration row" ;;
  automation) python3 "$T/submission_automation_matrix.py"; sed -n '1,180p' "$PH_HOME/SUBMISSION_AUTOMATION_MATRIX.md"; echo "next → ph submitted --check" ;;
  gates)    python3 "$T/founder_auth_dashboard.py"; sed -n '1,180p' "$PH_HOME/FOUNDER_AUTH_DASHBOARD.md"; echo "next → clear one gate, then ph submitted --check && ph tick" ;;
  profile)  python3 "$T/operator_profile.py" "$@"; sed -n '1,180p' "$PH_HOME/OPERATOR_PROFILE_DRAFT.md" ;;
  agents)   python3 "$T/agent_usage.py" "$@"; echo "next → adjust AGENT_USAGE_POLICY.tsv or route with ph dispatch <agent> \"<task>\"" ;;
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
  gap)      k="${1:?ph gap <key> \"<name>\"}"; n="${2:?need name}"; shift 2
            python3 "$T/prize_gap_loop.py" --key "$k" --name "$n" "$@"; echo "next → ph collab $k \"$n\" or ph plan $k \"$n\"" ;;
  tick)     bash "$T/portfolio_tick.sh" ;;
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
  doctor)   bash "$PH_HOME/ph_next.sh" --doctor 2>/dev/null || { echo "checking tools..."; for f in "$T"/*.sh; do bash -n "$f" 2>/dev/null || echo "  ❌ syntax: $(basename "$f")"; done; echo "done"; } ;;
  *) echo "unknown verb: $v"; exec "$0" help ;;
esac
