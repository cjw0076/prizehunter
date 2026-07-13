#!/usr/bin/env python3
"""Create a Codex-led creative / Claude-led build workloop for a campaign.

This is the collaboration lane requested by the operator:

1. Codex acts as creative director: ideas, source research, prior winners,
   reference assets, brand/visual direction, and the 120% quality bar.
2. Claude acts as the main builder/completer.
3. Gemini/local/other agents are used continuously for divergence, critique,
   web-grounded scouting, and blocker fallback.

The script writes durable packets first. Real dispatch is opt-in with --execute.
External submission, account signup, ToS, spend, and final portal actions remain
founder-gated.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
DISPATCH = CONTROL / "tools" / "agent_dispatch.sh"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S KST")


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")


def packet_header(role: str, key: str, name: str) -> str:
    return f"""# Packet — {role}

- campaign: `{key}`
- contest: {name}
- generated: {now()}
- rule: no external submission/account/ToS/spend action without founder gate
"""


def codex_packet(key: str, name: str, domain: str, platform: str, url: str) -> str:
    return packet_header("Codex Creative Director", key, name) + f"""

## Mission

Own the creative/research front of this campaign. Turn the contest into a
judge-winning direction before Claude builds.

## Inputs

- platform: {platform}
- domain: {domain}
- source_url: {url or "TBD"}
- local campaign dir: `competitions/control_tower/campaigns/{key}/`
- required gap loop: `competitions/control_tower/campaigns/{key}/PRIZE_GAP_LOOP.md`

## Required Output

Create `CREATIVE_BRIEF.md` with:

1. Official rules and eligibility summary with source links.
2. Deadline, submission fields, file limits, judging rubric, and disqualifiers.
3. Previous winners / organizer preference research.
4. Ten idea routes, including at least three non-obvious cross-domain routes.
5. Chosen route with kill criteria and why it can beat generic submissions.
6. Brand and visual direction: character/identity cues, reference assets,
   screenshot style, deck/video tone, and what must be visibly memorable.
7. Data/API/reference asset inventory with license and provenance.
8. 120% quality checklist: what the contest asks for vs what we will add.
9. Claude build contract: exact deliverables, folder targets, smoke tests,
   package names, and founder gates.
10. Deficiency closure map: each P0/P1 item from `PRIZE_GAP_LOOP.md` mapped to
    a concrete artifact or a documented kill/park decision.

## Routing Rule

Use `ph dispatch gemini "<bounded critique task>"` or registered web/research
agents for disagreement and breadth. Keep raw private data and secrets out of
packets. Record reusable assets with `record_asset_receipt.sh`.
"""


def gemini_packet(key: str, name: str, domain: str, platform: str, url: str) -> str:
    return packet_header("Gemini / External Challenge Scout", key, name) + f"""

## Mission

Challenge Codex's likely direction before build. Find better, stranger, or more
judge-aligned routes.

## Task

For `{name}` ({platform}, {domain}, {url or "TBD"}):

- Identify organizer intent, public examples, and prior winner patterns.
- Propose 12 routes, including 5 outside the obvious AI/data framing.
- Name the top 3 and the fastest proof for each.
- Attack weak assumptions, rights/IP risks, eligibility risks, and visual risks.
- Return only recommendations, sources, and blockers. Do not edit files.

## Stop

Stop at recommendation if a source requires login, payment, personal data,
account creation, or ToS acceptance.
"""


def claude_packet(key: str, name: str, domain: str, platform: str, url: str) -> str:
    return packet_header("Claude Main Builder", key, name) + f"""

## Mission

Use Codex's `CREATIVE_BRIEF.md` as the build contract and complete the campaign
artifact package to submission-ready quality.

## Required Local Context

- `competitions/control_tower/campaigns/{key}/CREATIVE_BRIEF.md`
- `competitions/control_tower/campaigns/{key}/PRIZE_GAP_LOOP.md`
- `competitions/control_tower/campaigns/{key}/COLLAB_WORKLOOP.md`
- `competitions/control_tower/AGENTS.md` if present, plus workspace AGENTS rules
- `competitions/control_tower/session_corpus/CORPUS_REPORT.md` when relevant

## Build Output

Produce a complete package appropriate to `{name}`:

- working prototype or validated analysis, if the contest rewards execution
- Korean/English submission text matched to the official form
- deck/script/video storyboard when useful
- visual/brand assets or screenshots when the contest is judged by presentation
- source/provenance appendix and reproducibility notes
- package zip/checksum when a file upload is expected
- `SUBMIT_FIELDS.md` with exact portal fields, leaving only founder-gated actions
- `DEFICIENCY_CLOSURE.md` showing which hidden-intent / 120% gaps were closed

## Blocker Loop

When blocked, do not stall. Create a short blocker packet and run:

```bash
AGENT=claude competitions/control_tower/tools/agent_dispatch.sh route --need "<blocker>"
AGENT=claude competitions/control_tower/tools/agent_dispatch.sh --to gemini --task "<bounded blocker packet>" --escalate codex,claude
```

Use Codex for implementation/repo edits if Claude cannot complete a coding
piece. Use Gemini/other web-capable agents for alternative ideas and external
checks. Founder-gate only external submission, account/ToS, credentials, spend,
or irreversible publication.
"""


def local_packet(key: str, name: str) -> str:
    return packet_header("Local / Cheap Bulk Agent", key, name) + f"""

## Mission

Cheap bounded extraction only. Never final acceptance.

## Allowed Work

- summarize rules copied into the packet
- label references and prior winners
- produce first-draft wording variants
- compress long notes into structured bullets

## Forbidden Work

- final claims, eligibility conclusions, legal/IP conclusions
- editing submission artifacts directly
- reading secrets, raw private logs, `.env`, auth stores, or account exports
"""


def workloop_doc(key: str, name: str, domain: str, platform: str, url: str) -> str:
    return f"""# Collaboration Workloop — {name}

- key: `{key}`
- platform: {platform}
- domain: {domain}
- source_url: {url or "TBD"}
- generated: {now()}

## Ownership

| Stage | Owner | Output | Gate |
|---|---|---|---|
| Creative/research direction | Codex | `CREATIVE_BRIEF.md` | source-backed, reusable, visual-first |
| Divergent challenge | Gemini / external smart agents | `CHALLENGE_NOTES.md` or dispatch log | recommendation only |
| Main build/completion | Claude | prototype/package/deck/submission fields | no external submit |
| Blocked piece | Best routed side agent | blocker-specific patch or advice | receipt required |
| Final closeout | Claude + Codex | QA, package, founder gate note, receipt | founder submits unless pre-approved |

## Operating Rule

Codex stays responsible for idea quality, research sharpness, reference assets,
brand/visual direction, and the 120% bar. Claude stays responsible for turning
the selected brief into finished artifacts. Gemini/local/other agents are
sidecars for breadth, contradiction, and blocked subproblems.

Before Codex writes the creative brief, run:

```bash
ph gap {key} "{name}" --platform {platform} --domain {domain} --url "{url or 'TBD'}"
```

## Packets

- `packets/codex_creative_director.md`
- `packets/gemini_challenge_scout.md`
- `packets/claude_main_builder.md`
- `packets/local_bulk_agent.md`

## Dispatch Examples

```bash
AGENT=codex competitions/control_tower/ph dispatch gemini "$(cat competitions/control_tower/campaigns/{key}/packets/gemini_challenge_scout.md)"
AGENT=codex competitions/control_tower/ph dispatch claude "$(cat competitions/control_tower/campaigns/{key}/packets/claude_main_builder.md)"
```

## Founder Gates

- portal submission / final submit button
- account signup, login, ToS, or personal/KYC data
- paid APIs, cloud spend, sponsorship/entry fees
- irreversible public publication
"""


def dispatch(agent: str, task_path: Path, execute: bool) -> None:
    mode = [] if execute else ["--dry-run"]
    task = task_path.read_text(encoding="utf-8")
    cmd = [str(DISPATCH), "--to", agent, "--task", task, *mode]
    env = os.environ.copy()
    env["AGENT"] = env.get("AGENT", "codex-collab")
    subprocess.run(cmd, cwd=CONTROL.parents[1], env=env, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--domain", default="general")
    ap.add_argument("--platform", default="unknown")
    ap.add_argument("--url", default="")
    ap.add_argument("--execute", action="store_true", help="actually dispatch Gemini and Claude")
    ap.add_argument("--dispatch", choices=["none", "challenge", "build", "all"], default="none")
    args = ap.parse_args()

    base = CONTROL / "campaigns" / args.key
    packets = base / "packets"
    write(base / "COLLAB_WORKLOOP.md", workloop_doc(args.key, args.name, args.domain, args.platform, args.url))
    write(packets / "codex_creative_director.md", codex_packet(args.key, args.name, args.domain, args.platform, args.url))
    write(packets / "gemini_challenge_scout.md", gemini_packet(args.key, args.name, args.domain, args.platform, args.url))
    write(packets / "claude_main_builder.md", claude_packet(args.key, args.name, args.domain, args.platform, args.url))
    write(packets / "local_bulk_agent.md", local_packet(args.key, args.name))

    manifest = {
        "key": args.key,
        "name": args.name,
        "platform": args.platform,
        "domain": args.domain,
        "source_url": args.url,
        "generated": now(),
        "roles": {
            "codex": "creative director, research, references, visual/brand direction, 120% brief",
            "claude": "main builder/completer, package and submission fields",
            "gemini": "divergent ideas, web-grounded challenge, blocker sidecar",
            "local": "cheap bounded extraction and summaries only",
        },
        "founder_gates": ["external_submit", "account_tos_login", "credentials", "spend", "irreversible_publication"],
    }
    write(base / "AGENT_SWARM.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    print(base / "COLLAB_WORKLOOP.md")
    print(packets / "codex_creative_director.md")
    print(packets / "gemini_challenge_scout.md")
    print(packets / "claude_main_builder.md")
    print(f"mode={'EXECUTE' if args.execute else 'DRY-RUN'} dispatch={args.dispatch}")

    if args.dispatch in {"challenge", "all"}:
        dispatch("gemini", packets / "gemini_challenge_scout.md", args.execute)
    if args.dispatch in {"build", "all"}:
        dispatch("claude", packets / "claude_main_builder.md", args.execute)

    print(
        textwrap.dedent(
            f"""
            next -> Codex fills campaigns/{args.key}/CREATIVE_BRIEF.md, then:
                    ph collab {args.key} "{args.name}" --dispatch all --execute
            """
        ).strip()
    )


if __name__ == "__main__":
    main()
