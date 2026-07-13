#!/usr/bin/env python3
"""Submission automation capability matrix for prizehunter."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
ROOT = CONTROL.parents[1]
OUT = CONTROL / "SUBMISSION_AUTOMATION_MATRIX.md"


MATRIX = [
    {
        "platform": "DACON API",
        "level": "A5 for delegated daily leaderboard submits",
        "implemented": "yes",
        "paths": "campaigns/<key>/submit.sh (your per-competition submit script)",
        "evidence": "campaigns/<key>/artifacts/submission_log.jsonl",
        "gap": "Needs valid token/team/contest permission; final/private pick still requires strategy discipline.",
    },
    {
        "platform": "Kaggle CLI",
        "level": "A4/A5 when rules/auth delegation is already cleared",
        "implemented": "yes, per-contest",
        "paths": "competitions/control_tower/campaigns/orbit-wars/WORKLOG.md; tools/kaggle_auth.sh",
        "evidence": "orbit-wars v7/v10/v12 submission refs in WORKLOG; `kaggle competitions submissions -c orbit-wars` verification notes",
        "gap": "No generic Kaggle submit orchestrator yet; join/rules acceptance remains founder/delegation-gated.",
    },
    {
        "platform": "Devpost Playwright",
        "level": "A3 draft fill; A4 verification with live session; A5 only with standing delegation",
        "implemented": "partial",
        "paths": "competitions/control_tower/tools/devpost_submit.py; tools/devpost_submissions.json; tools/browser_login.sh",
        "evidence": "/tmp/devpost_current_verify/*.png; /tmp/devpost_shots/*.png when run",
        "gap": "Script intentionally stops before final Submit. Need per-hackathon final-submit adapters + standing-delegation receipts.",
    },
    {
        "platform": "Korean web portals",
        "level": "A3 package + receipt verification; A4/A5 ad hoc only",
        "implemented": "partial/ad hoc",
        "paths": "campaigns/moct_ai_data; ai_case_contest_2026/_제출_aicase; receipts/*portal-submitted*.md",
        "evidence": "/tmp/ai_case_04_after_submit.png; /tmp/moct_verify_current3/result.png; portal receipts",
        "gap": "No generic Playwright upload adapter for culture.go.kr/datacontest.kr/ai.software.kr. Signatures, identity, ToS, and final upload remain gated unless explicitly delegated.",
    },
    {
        "platform": "AIcrowd / ARC Whitebox",
        "level": "A2/A3 local validation/package",
        "implemented": "local harness only",
        "paths": "campaigns/arc-whitebox-2026/RUNBOOK_20260615.md; upstream/whest-starterkit; submission_covariance_baseline_20260615.tar.gz",
        "evidence": "whest validate/run/package logs in campaigns/arc-whitebox-2026",
        "gap": "No external AIcrowd submit automation yet. Add only after rules/session/delegation are explicit.",
    },
    {
        "platform": "Credential-gated challenge APIs",
        "level": "A1/A2 recon unless credential/session exists",
        "implemented": "blocked receipts + smoke scripts",
        "paths": "kdd-unirec-2026; zindi-worldcup-2026; neurogolf-2026; adia-structural-break-rt",
        "evidence": "DATA_ACCESS_RECEIPT/FULL_DATA_ACCESS_RECEIPT/failure_reports",
        "gap": "Need platform tokens/sessions before API submit/download can be systematized.",
    },
]


def yesno(cmd: str) -> str:
    return "yes" if shutil.which(cmd) else "missing"


def table(rows: list[dict[str, str]], cols: list[tuple[str, str]]) -> list[str]:
    out = ["| " + " | ".join(label for _, label in cols) + " |"]
    out.append("|" + "|".join("---" for _ in cols) + "|")
    for row in rows:
        out.append("| " + " | ".join(row.get(k, "-").replace("|", "\\|") for k, _ in cols) + " |")
    return out


def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    md = [
        "# Submission Automation Matrix",
        "",
        f"_generated: {now}_",
        "",
        "This answers what prizehunter can actually submit, verify, or only prepare. It is intentionally conservative about legal/account/ToS/signature/spend gates.",
        "",
        "## Local Tool Availability",
        "",
        "| tool | available |",
        "|---|---|",
    ]
    for cmd in ["playwright", "node", "npx", "kaggle", "gh", "python3"]:
        md.append(f"| `{cmd}` | {yesno(cmd)} |")
    md += [
        "",
        "## Platform Matrix",
        "",
    ]
    md += table(
        MATRIX,
        [
            ("platform", "platform"),
            ("level", "current automation level"),
            ("implemented", "implemented"),
            ("paths", "implementation paths"),
            ("evidence", "evidence"),
            ("gap", "remaining gap"),
        ],
    )
    md += [
        "",
        "## A-Level Legend",
        "",
        "- `A1`: recon only.",
        "- `A2`: local build/validation.",
        "- `A3`: package/draft ready.",
        "- `A4`: authenticated upload/check/receipt possible.",
        "- `A5`: final external submit possible only with explicit standing delegation or pre-approved daily-submit automation.",
        "",
        "## Operating Rule",
        "",
        "APIs should be used whenever a platform exposes a stable API or CLI and credentials are already delegated. Browser/Playwright is the fallback for portals without usable APIs. Final submit, ToS, signup, payment, signature, and identity commitments remain gated unless a contest-specific standing-delegation receipt exists.",
    ]
    OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
