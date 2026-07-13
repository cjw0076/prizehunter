#!/usr/bin/env python3
"""Materialize ranked next-pool candidates into campaign work folders.

This turns NEXT_COMPETITION_POOL.tsv into durable prizehunter campaigns:

- PLAN.md / PLAN.json through plan_campaign.py
- PRIZE_GAP_LOOP.md through prize_gap_loop.py
- COLLAB_WORKLOOP.md + dispatch packets through collab_workloop.py
- CREATIVE_DIRECTOR_BRIEF.md for Codex-led creative/design/literature/idea work
- RECON_SOURCES.md and AGENT_WORKLOG.md stubs

External submissions, account/ToS, spend, and credentials remain founder-gated.
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
from datetime import datetime
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
TOOLS = CONTROL / "tools"
POOL = CONTROL / "NEXT_COMPETITION_POOL.tsv"
CAMPAIGNS = CONTROL / "campaigns"


CREATIVE_KINDS = {"media", "text", "idea", "vision", "art_culture", "other"}


def slug(value: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", value.strip()).strip("-").lower()
    base = re.sub(r"-+", "-", base)
    return base[:80] or "campaign"


def read_pool() -> list[dict[str, str]]:
    with POOL.open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=CONTROL.parents[1], check=True)


def is_creative(row: dict[str, str]) -> bool:
    if row.get("creative_owner") == "codex_creative_director":
        return True
    blob = f"{row.get('kind','')} {row.get('name','')}"
    return bool(
        row.get("kind") in CREATIVE_KINDS
        or re.search("문학|문예|독후감|스토리|웹툰|디자인|영상|아트|예술|건축|브랜드|캐릭터|창작", blob)
    )


def creative_brief(row: dict[str, str]) -> str:
    name = row["name"]
    return f"""# Codex Creative Director Brief — {name}

- generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}
- key: `{row['key']}`
- priority: {row.get('priority')}
- score: {row.get('score')}
- source: {row.get('source')}
- kind: {row.get('kind')}
- prize_krw: {row.get('prize_krw')}
- deadline: {row.get('deadline')}
- url: {row.get('url')}

## Codex Ownership

Codex owns the creative strategy for this campaign: idea routes, research angle,
reference mining, brand/character/visual system, deck/video/storyboard style,
and visual QA. Claude should not start final build until this brief has a
selected route and deficiency-closure map.

## 120% Creative Standard

If the contest asks for a file, we ship a file plus rationale, provenance,
presentation board, and judge-ready explanation. If it asks for an idea, we ship
a plausible product/service/business or policy package. If it asks for writing,
we ship author dossier, portfolio/activity record, revision log, and compliance.
If it asks for design/video/art, we ship a visual bible, reference board,
storyboard/key frames, thumbnail test, and rights-safe asset ledger.

## Required Research

- Official rules, eligibility, deadline, submission fields, file size/format.
- Judging rubric and hidden intent: what first place must prove beyond the text.
- Prior winners, organizer press releases, social posts, and recurring themes.
- AI-use, copyright, model disclosure, and asset provenance constraints.
- Competitor baseline: what a generic 100% submission would look like.

## Idea Routes

| route | premise | why non-obvious | proof artifact | kill criterion |
|---|---|---|---|---|
| R1 | TBD | TBD | TBD | TBD |
| R2 | TBD | TBD | TBD | TBD |
| R3 | TBD | TBD | TBD | TBD |
| R4 | TBD | TBD | TBD | TBD |
| R5 | TBD | TBD | TBD | TBD |

## Visual System

- Brand/working title:
- Character or motif:
- Palette:
- Typography:
- Composition language:
- Image/video reference families:
- Thumbnail rule:
- Deck/storyboard tone:
- Do-not-use list:

## External Agent Use

- Gemini/external smart agent: divergent route challenge and overclaim check.
- Claude: main package build after Codex locks route.
- Local LLM: cheap extraction/summarization only.

## Deliverables To Hand Claude

- Selected route and rationale.
- Final asset/reference inventory with licenses/provenance.
- `DEFICIENCY_CLOSURE.md` checklist target.
- Submission copy outline.
- Visual/storyboard/deck requirements.
- Founder gates: account/ToS/submission/spend/credential only.
"""


def recon_sources(row: dict[str, str]) -> str:
    return f"""# Recon Sources — {row['name']}

Primary URL: {row.get('url') or 'TBD'}

## Source Queue

- Official rules page
- Submission form / FAQ
- Organizer announcements and press releases
- Previous winners / finalist galleries
- Sponsor/platform documentation
- Rights, AI-use, and eligibility clauses

## Notes

{row.get('note','')}
"""


def worklog(row: dict[str, str]) -> str:
    return f"""# Agent Worklog — {row['name']}

## {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')} materialized

- agent: Codex
- action: materialized ranked next-pool candidate into a prizehunter campaign folder.
- priority: {row.get('priority')} score={row.get('score')} kind={row.get('kind')}
- source: {row.get('source')} {row.get('url')}
- owner model: {'Codex creative director first, Claude main build second' if is_creative(row) else 'Codex recon/build loop, Claude review/build support'}
- next: complete `CREATIVE_DIRECTOR_BRIEF.md` if creative, then dispatch challenge/build packets.
"""


def materialize(row: dict[str, str], execute_tools: bool) -> Path:
    key = row["key"]
    base = CAMPAIGNS / key
    base.mkdir(parents=True, exist_ok=True)
    (base / "RECON_SOURCES.md").write_text(recon_sources(row), encoding="utf-8")
    if not (base / "AGENT_WORKLOG.md").exists():
        (base / "AGENT_WORKLOG.md").write_text(worklog(row), encoding="utf-8")
    else:
        with (base / "AGENT_WORKLOG.md").open("a", encoding="utf-8") as f:
            f.write("\n" + worklog(row))
    if is_creative(row):
        (base / "CREATIVE_DIRECTOR_BRIEF.md").write_text(creative_brief(row), encoding="utf-8")
    if execute_tools:
        run(
            [
                "python3",
                str(TOOLS / "plan_campaign.py"),
                "--key",
                key,
                "--name",
                row["name"],
                "--domain",
                row.get("kind") or "general",
                "--metric",
                "judged" if row.get("kind") not in {"ml", "build"} else "n/a",
                "--platform",
                row.get("source") or "unknown",
                "--prize",
                row.get("prize_krw") or "",
            ]
        )
        run(
            [
                "python3",
                str(TOOLS / "prize_gap_loop.py"),
                "--key",
                key,
                "--name",
                row["name"],
                "--domain",
                row.get("kind") or "general",
                "--platform",
                row.get("source") or "unknown",
                "--url",
                row.get("url") or "",
            ]
        )
        run(
            [
                "python3",
                str(TOOLS / "collab_workloop.py"),
                "--key",
                key,
                "--name",
                row["name"],
                "--domain",
                row.get("kind") or "general",
                "--platform",
                row.get("source") or "unknown",
                "--url",
                row.get("url") or "",
            ]
        )
    return base


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--min-score", type=int, default=85)
    ap.add_argument("--execute-tools", action="store_true")
    args = ap.parse_args()

    rows = []
    for row in read_pool():
        row["key"] = row.get("id") or f"{row.get('source','pool')}-{slug(row.get('name',''))}"
        try:
            score = int(row.get("score") or 0)
        except ValueError:
            score = 0
        if score >= args.min_score:
            rows.append(row)
    rows = rows[: args.limit]

    for row in rows:
        path = materialize(row, args.execute_tools)
        print(f"{row.get('priority')} score={row.get('score')} {row['key']} -> {path}")
    print(f"materialized={len(rows)}")


if __name__ == "__main__":
    main()
