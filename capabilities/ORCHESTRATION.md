# Orchestration — agent-agnostic

**Whoever you are** (claude, codex, gemini, qwen, kimi, a local model — running
as the user's *main* agent), you are the conductor when you read this. The system
does not assume any one vendor orchestrates. These are plain files + shell tools,
so any CLI agent drives them identically.

## On entry (every agent, first thing)

```bash
bash competitions/control_tower/tools/agent_bootstrap.sh   # prints system map + who's installed
bash competitions/control_tower/capabilities/refresh_capabilities.sh   # probe installs
```

Then **self-author your own card**: write the sections only you can see (your
skills, MCP servers, slash commands, subagents) into
`capabilities/<you>.card.md`. A shell can't enumerate model-injected
capabilities — only you can. Keep probe-facts + self-authored facts both present.

## To get unblocked / get help (the core loop)

You are never stuck alone. When blocked, or when another agent is better suited:

```bash
# 1. who's best for this need?
bash .../tools/agent_dispatch.sh route --need "heavy implementation"

# 2. hand it off (with fallback chain if the first is down/blocked)
AGENT=<you> bash .../tools/agent_dispatch.sh --to codex \
  --task "implement X per brief Y" --escalate gemini,claude
```

The bus checks the target is installed, runs it headless, captures output,
records an AIOS receipt, and escalates down the chain on failure. Set `AGENT=`
to your own name so the receipt shows who asked.

## Default prizehunter collaboration lane

For creative, visual, idea, research, design, writing, case-study, and
open-ended hackathon competitions, use this lane unless a campaign overrides it:

- **Codex = creative director / research closer.** Codex owns idea routes,
  source research, prior winners, reference assets, brand/visual direction,
  quality bar, and the build contract.
- **Claude = main builder / completer.** Claude turns the Codex brief into the
  working artifact package: prototype, writeup, deck/script, screenshots,
  submission fields, package zip, and closeout receipt.
- **Gemini + other smart agents = sidecars.** Use them continuously for
  divergence, outside-reader critique, web-grounded scouting, and blocked
  subproblems.
- **Local/cheap LLMs = bounded extraction only.** They may summarize copied
  rules, label references, or draft variants, but never make final claims.

Start this lane with:

```bash
ph collab <key> "<contest name>" --platform <platform> --domain <domain> --url <official-url>
```

Then Codex fills `campaigns/<key>/CREATIVE_BRIEF.md`; Claude builds from that
brief. If a sidecar is needed:

```bash
ph collab <key> "<contest name>" --dispatch challenge     # dry-run packet
ph collab <key> "<contest name>" --dispatch all --execute # real dispatch
```

## Shared opinion workspace

Use `ph discuss` when an opinion, critique, or decision should survive beyond a
single dispatch log:

```bash
ph discuss init
ph discuss post --topic "contest route" --kind proposal --agent codex --campaign <key> --message "..."
ph discuss post --topic "contest route" --kind critique --agent gemini --campaign <key> --message "..."
ph discuss decision --topic "contest route" --agent codex --campaign <key> --message "Accepted route and why."
ph discuss list
```

Campaign work stays in `campaigns/<key>/COLLAB_WORKLOOP.md`; cross-campaign
debate, dissent, and final rationale go in `agent_workspace/`.

## Team-mode workspace

Use `ph team` when multiple human teammates and their agents share Prizehunter.
This writes dashboard-visible comms and keeps team membership in
`TEAM_ROSTER.tsv` without storing private contact or credential data.

```bash
ph team init --target /path/to/Dacon
ph team onboard --agent codex-b --human-label teammate-b \
  --role builder --route-to "tabular experiments and ablations" \
  --target /path/to/Dacon
ph team checkin --from codex-b --competition <key> \
  --done "what changed" --next "next validation" --blocker "none"
ph team review --from gemini --to codex --competition <key> \
  --verdict challenge --body "why this may lose, evidence needed, kill rule"
ph team idea --from scout-a --competition <key> \
  --topic "cross-domain route" --body "idea and source/evidence"
```

Team rules live in `TEAM_OPERATING_SYSTEM.md`. The invariant is simple: every
teammate owns a stable agent alias, writes only that alias's comms/run files, and
uses `ph discuss decision` for accepted strategic decisions.

## Routing heuristics (from capability cards)

- **Creative direction / idea synthesis / source research / visual reference system → codex**
- **Main artifact build / completion / long-context synthesis / final package → claude**
- **Heavy implementation / parallel fan-out / sandboxed exec fallback → codex**
- **Alt ideas / web-grounded scouting / cheap second opinion / challenge → gemini**
- **Cheap bulk / offline / private → qwen | kimi | local** (install first)
- **Stuck on a ceiling claim?** dispatch the SAME problem to a *different vendor*
  and have it try to refute you (METHODOLOGY Phase 4b: adversarial triangulation).

## Usage mix control

Prizehunter should not become accidentally Claude-only, Codex-only, or one-track.
Use:

```bash
ph agents
ph route "<task>"
```

`ph agents` compares durable dispatch receipts/logs with
`AGENT_USAGE_POLICY.tsv`. `ph route` applies the cheap-first ladder in
`TOKEN_SAVING_POLICY.md` before dispatch. Treat shares as operating targets, not
hard quotas: route by fit first, then rebalance with sidecar critique, scouting,
bulk extraction, or implementation fallback. If an agent is over `max_share`,
use it only when uniquely fitted or time-critical. If an agent is below half its
target and has a matching role, dispatch a bounded task to it before deepening
the same line of thought.

## Use external knowledge & data aggressively

Before grinding, dispatch a scouting query: web search (your own tool, or
gemini's web grounding), the discovery report, the mined session corpus
(`session_corpus/CORPUS_REPORT.md` = what worked/failed before), and MCP servers
(HuggingFace for datasets/models, etc.). Cite what you used in the receipt.

## Invariants (any orchestrator must honor)

- Recommendation-only; outward-facing/irreversible actions stay founder-gated.
- Record every dispatch + decision (the bus does this automatically).
- No secrets in cards/receipts. Privacy boundaries inviolable.
- Name a stop condition before dispatching an autonomous chain.

## Plug in ANY new CLI agent (hermes, cursor, grok, ...) — one line
```bash
tools/agent_dispatch.sh add grok --dispatch 'grok -p {TASK}' \
  --vendor xai --tier mid --route-to "real-time/web info, fast reasoning"
```
`{TASK}` (and optional `{MODEL}`) are substituted at dispatch. Install status is
auto-detected. After adding, the agent is immediately routable/dispatchable and
should self-author its `<name>.card.md`. Registered so far: claude, codex, gemini,
cursor, hermes (installed) + grok (pluggable when CLI present).
