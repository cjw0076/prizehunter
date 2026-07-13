#!/usr/bin/env python3
"""Build a privacy-safe operator profile draft for Prizehunter.

This is not a personal dossier. It is a working model of the operator's
competition preferences, delegation style, risk boundaries, and recurring
interests inferred from local project metadata and prizehunter records.

Default behavior avoids reading arbitrary file contents. It uses:
- portfolio_registry.tsv
- top-level git repo names/remotes under the workspace
- competition/control-tower metadata

Secrets, raw private logs, .env files, provider auth stores, and detailed
personal identifiers are never copied into the output.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


CONTROL = Path(__file__).resolve().parents[1]
ROOT = CONTROL.parents[1]
WORKSPACE = ROOT.parent
REGISTRY = CONTROL / "portfolio_registry.tsv"
OUT_MD = CONTROL / "OPERATOR_PROFILE_DRAFT.md"
OUT_JSON = CONTROL / "OPERATOR_PROFILE_DRAFT.json"

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "v5.2",
    "artifacts",
}

SECRETISH = re.compile(
    r"(?i)(token|secret|password|passwd|cookie|session|credential|apikey|api_key|\.env|keyring|auth)"
)


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def run_git(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def redact_remote(url: str) -> str:
    url = re.sub(r"//[^/@]+@", "//<redacted>@", url)
    url = re.sub(r"(token|password|access_token)=([^&]+)", r"\1=<redacted>", url, flags=re.I)
    return url


def read_registry() -> list[dict[str, str]]:
    if not REGISTRY.exists():
        return []
    with REGISTRY.open(encoding="utf-8", errors="ignore", newline="") as f:
        lines = (line for line in f if line.strip() and not line.startswith("#"))
        return list(csv.DictReader(lines, delimiter="\t"))


def repo_summary(workspace: Path) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    for gitdir in sorted(workspace.glob("*/.git")):
        repo = gitdir.parent
        if SECRETISH.search(repo.name):
            continue
        remotes_raw = run_git(repo, ["remote", "-v"])
        remotes = sorted({redact_remote(line) for line in remotes_raw.splitlines() if line.strip()})
        branch = run_git(repo, ["branch", "--show-current"]) or "-"
        status = run_git(repo, ["status", "--short"])
        repos.append(
            {
                "name": repo.name,
                "path": str(repo.relative_to(workspace)),
                "branch": branch,
                "dirty": bool(status),
                "remotes": remotes[:4],
            }
        )
    return repos


def extension_counts(base: Path, limit: int = 4000) -> Counter[str]:
    counts: Counter[str] = Counter()
    seen = 0
    for path in base.rglob("*"):
        if seen >= limit:
            break
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(base).parts)
        if rel_parts & SKIP_DIRS:
            continue
        if SECRETISH.search(str(path)):
            continue
        suffix = path.suffix.lower() or "<none>"
        counts[suffix] += 1
        seen += 1
    return counts


def infer_from_registry(rows: list[dict[str, str]]) -> dict[str, Any]:
    status = Counter(r.get("status", "") for r in rows if r.get("status"))
    metrics = Counter(r.get("metric", "") for r in rows if r.get("metric"))
    active = [r for r in rows if r.get("status") in {"active", "submitted", "ready-gate", "blocked"}]
    submitted = [r for r in rows if r.get("status") == "submitted"]
    next_text = " ".join(r.get("next_lever", "") for r in rows)
    blocker_text = " ".join(r.get("blocker", "") for r in rows)

    interests = Counter()
    keywords = {
        "leaderboard/data science": r"\bleaderboard|DACON|Kaggle|score|CV|OOF|submission",
        "agent systems": r"\bagent|tool|workflow|automation|AIcrowd|Devpost",
        "public-data products": r"공공데이터|public data|operator|walkthrough|dashboard",
        "creative/invention contests": r"idea|design|visual|video|creative|invention|architecture",
        "memory/control plane": r"memory|AIOS|ledger|receipt|Notion|Hermes",
        "founder-gate delegation": r"FOUNDER|auth|login|ToS|upload|registration|submit",
    }
    hay = f"{next_text} {blocker_text}"
    for label, pattern in keywords.items():
        interests[label] += len(re.findall(pattern, hay, flags=re.I))

    return {
        "status_counts": dict(status),
        "metric_counts": dict(metrics),
        "active_keys": [r.get("key", "") for r in active[:30]],
        "submitted_keys": [r.get("key", "") for r in submitted],
        "interest_signals": dict(interests),
    }


def build_profile(workspace: Path) -> dict[str, Any]:
    rows = read_registry()
    repos = repo_summary(workspace)
    ext_counts = extension_counts(workspace)
    registry = infer_from_registry(rows)

    repo_names = {r["name"] for r in repos}
    hypotheses = [
        {
            "claim": "The operator values autonomous execution, but wants explicit tracking and receipts for every irreversible or ambiguous action.",
            "evidence": ["portfolio_registry founder gates", "submission board strict audit", "repeated user requests for tracking/dashboard"],
            "confidence": "high",
        },
        {
            "claim": "The operator prefers high-EV prize hunting across domains rather than staying inside a single ML competition niche.",
            "evidence": ["portfolio contains data, hackathon, idea/design, finance, public-data, ARC/agent tracks"],
            "confidence": "high",
        },
        {
            "claim": "The operator rewards strategic depth: hidden evaluation geometry, cross-domain analogies, and non-obvious data/manual levers.",
            "evidence": ["Strategic Depth Protocol", "wind-power missing-data analogy", "latest instruction about writing new standards"],
            "confidence": "high",
        },
        {
            "claim": "The operator runs a multi-competition portfolio, not one-off contests.",
            "evidence": sorted(repo_names)[:5],
            "confidence": "high",
        },
        {
            "claim": "The operator dislikes shallow fast outputs when they reduce win probability; speed is useful only when paired with verification.",
            "evidence": ["quality gate tooling", "completion reviews", "user concern about too-fast low-quality outputs"],
            "confidence": "high",
        },
    ]

    routing = [
        "Before broad build work, ask: what is the hidden scoring/rubric geometry and what would a strong human team do manually?",
        "Default to autonomous action, but surface external legal/ToS/spend/identity gates as named gates with retry commands.",
        "For each failure, record root cause, changed retry route, and what not to repeat.",
        "Prefer dashboards/receipts/append-only logs over chat-only memory.",
        "Use cross-model/agent challenge for taste, strategy, and ceiling claims; use focused local tests for implementation claims.",
    ]

    return {
        "generated_at": now(),
        "scope": str(workspace),
        "privacy": {
            "mode": "draft_only",
            "excluded": ["secrets", ".env", "cookies", "raw auth stores", "private credential values", "personal contact fields"],
            "content_policy": "working preferences only; no identity claims beyond operator-provided work context",
        },
        "workspace_repos": repos,
        "top_extensions": ext_counts.most_common(20),
        "registry_signals": registry,
        "operator_hypotheses": hypotheses,
        "agent_routing_rules": routing,
    }


def write_outputs(profile: dict[str, Any]) -> None:
    OUT_JSON.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Operator Profile Draft")
    lines.append("")
    lines.append(f"- generated: {profile['generated_at']}")
    lines.append("- status: draft only; not accepted MemoryOS truth")
    lines.append("- purpose: help Prizehunter choose routes, prompts, gates, and review style")
    lines.append("- privacy: excludes secrets, auth files, cookies, raw private exports, and personal contact fields")
    lines.append("")
    lines.append("## Workspace Signals")
    for repo in profile["workspace_repos"]:
        remote = "; ".join(repo.get("remotes", [])) or "-"
        lines.append(f"- `{repo['name']}` branch `{repo['branch']}` dirty={repo['dirty']} remote={remote}")
    lines.append("")
    lines.append("## Top File Types")
    lines.append(", ".join(f"`{ext}`={count}" for ext, count in profile["top_extensions"][:15]) or "-")
    lines.append("")
    lines.append("## Prizehunter Signals")
    reg = profile["registry_signals"]
    lines.append(f"- statuses: {reg['status_counts']}")
    lines.append(f"- submitted: {', '.join(reg['submitted_keys']) or '-'}")
    lines.append(f"- interest signals: {reg['interest_signals']}")
    lines.append("")
    lines.append("## Working Hypotheses")
    for item in profile["operator_hypotheses"]:
        evidence = "; ".join(item["evidence"])
        lines.append(f"- {item['claim']} _(confidence: {item['confidence']}; evidence: {evidence})_")
    lines.append("")
    lines.append("## Agent Routing Rules")
    for rule in profile["agent_routing_rules"]:
        lines.append(f"- {rule}")
    lines.append("")
    lines.append("## Review Rule")
    lines.append("Treat this as a draft model. Update or delete claims when the operator behavior contradicts them.")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=str(WORKSPACE))
    args = ap.parse_args()
    profile = build_profile(Path(args.workspace))
    write_outputs(profile)
    print(OUT_MD)
    print(OUT_JSON)
    print("next → review OPERATOR_PROFILE_DRAFT.md, then ph tick")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
