#!/usr/bin/env python3
"""Human-facing submission/operations board for prizehunter.

This intentionally separates "where the registry says we are" from "how a
human can confirm it". It must not print passwords, phone numbers, cookies, or
other private lookup values.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import datetime
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
ROOT = CONTROL.parents[1]
REGISTRY = CONTROL / "portfolio_registry.tsv"
OUT_MD = CONTROL / "SUBMISSION_BOARD.md"
OUT_TSV = CONTROL / "SUBMISSION_BOARD.tsv"
STRICT_STATUS_SOURCES = [
    CONTROL / "PORTFOLIO_STATUS.md",
    CONTROL / "STRATEGIST_BRIEF.md",
    CONTROL / "QUALITY_GATE_REPORT.md",
    CONTROL / "QUALITY_GATE_REPORT.tsv",
]


EXTRA: dict[str, dict[str, str]] = {}  # optional per-competition overlay; populate for your own comps

KNOWN_STATUS_CONFLICTS: list[dict[str, str]] = []

VISIBLE_STATUSES = {
    "submitted",
    "active",
    "ready-gate",
    "blocked",
    "ceiling",
    "recon",
    "scaffold",
}

RECEIPTS = CONTROL / "receipts"
GROUND_TRUTH = CONTROL / "CONDUCTOR_GROUND_TRUTH_SUBMISSIONS.md"
EVIDENCE_NAME_HINTS = ("submit", "confirm", "sent", "receipt", "accepted", "screenshot")


def locate_evidence(row: dict[str, str], gt_text: str) -> list[str]:
    """On-disk evidence for a submitted row. A miss means "evidence not recorded
    in this repo" — NEVER "not submitted" (Gmail/portal-side evidence is valid;
    see KNOWN_STATUS_CONFLICTS). This is the enforcement half of the anti-
    fabrication policy: a status flipped to submitted must come with a findable ref."""
    key = row["key"]
    found: list[str] = []
    for tok in re.split(r"[;\s]+", EXTRA.get(key, {}).get("evidence", "")):
        tok = tok.strip().rstrip(";,")
        if not tok:
            continue
        if re.fullmatch(r"[0-9a-f]{12,}", tok):
            found.append(f"gmail:{tok}")  # recorded message-id counts as a pointer
            continue
        if "/" not in tok:
            continue
        cand = Path(tok) if tok.startswith("/") else ROOT / tok
        if cand.exists():
            found.append(tok)
    if RECEIPTS.is_dir():
        kl = key.lower()
        for f in sorted(RECEIPTS.iterdir()):
            n = f.name.lower()
            if kl in n and any(h in n for h in EVIDENCE_NAME_HINTS):
                found.append(f"receipts/{f.name}")
                if len(found) >= 8:
                    break
    if gt_text and key in gt_text:
        found.append("CONDUCTOR_GROUND_TRUTH_SUBMISSIONS.md")
    return found


def evidence_audit(submitted: list[dict[str, str]]) -> list[dict[str, str]]:
    gt_text = GROUND_TRUTH.read_text(encoding="utf-8", errors="ignore") if GROUND_TRUTH.exists() else ""
    out = []
    for r in submitted:
        found = locate_evidence(r, gt_text)
        out.append({
            "key": r["key"],
            "verdict": "VERIFIED-ON-DISK" if found else "UNVERIFIED (증거 미기록 — 미제출 단정 아님)",
            "found": "; ".join(found[:4]) if found else "-",
        })
    return out


def read_registry() -> list[dict[str, str]]:
    with REGISTRY.open(encoding="utf-8", errors="ignore", newline="") as f:
        lines = (
            line
            for line in f
            if line.strip() and not line.lstrip().lstrip('"').startswith("#")
        )
        return [{k: (v or "") for k, v in row.items()} for row in csv.DictReader(lines, delimiter="\t")]


def registry_status_map(rows: list[dict[str, str]]) -> dict[str, str]:
    return {r["key"]: r.get("status", "") for r in rows if r.get("key")}


def parse_md_table_status(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    out: list[dict[str, str]] = []
    header: list[str] | None = None
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
        low = [c.lower() for c in cells]
        if "competition" in low or "key" in low:
            header = low
            continue
        if not header:
            continue
        key = status = ""
        if "competition" in header:
            key = cells[header.index("competition")]
        elif "key" in header:
            key = cells[header.index("key")]
        if "status" in header:
            status = cells[header.index("status")]
        if key and status:
            out.append({"source": str(path.relative_to(ROOT)), "key": key, "status": status})
    return out


def parse_tsv_status(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="ignore", newline="") as f:
        rows = list(csv.DictReader((line for line in f if line.strip() and not line.startswith("#")), delimiter="\t"))
    out = []
    for row in rows:
        key = row.get("key", "")
        status = row.get("status", "")
        if key and status:
            out.append({"source": str(path.relative_to(ROOT)), "key": key, "status": status})
    return out


def strict_status_audit(registry_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    registry = registry_status_map(registry_rows)
    mismatches: list[dict[str, str]] = []
    for path in STRICT_STATUS_SOURCES:
        observed = parse_tsv_status(path) if path.suffix == ".tsv" else parse_md_table_status(path)
        for item in observed:
            key = item["key"]
            if key not in registry:
                continue
            expected = registry[key]
            actual = item["status"]
            if actual != expected:
                mismatches.append(
                    {
                        "source": item["source"],
                        "key": key,
                        "registry": expected,
                        "observed": actual,
                        "action": "regenerate the source from portfolio_registry.tsv or update the registry with evidence",
                    }
                )
    return mismatches


def clip(text: str, n: int = 180) -> str:
    text = " ".join((text or "-").split())
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "..."


def linkish(value: str) -> str:
    return value or "-"


def enrich(row: dict[str, str]) -> dict[str, str]:
    extra = EXTRA.get(row["key"], {})
    return {
        **row,
        "name": extra.get("name", row["key"]),
        "official": extra.get("official", "-"),
        "project": extra.get("project", "-"),
        "repo": extra.get("repo", "-"),
        "demo": extra.get("demo", "-"),
        "video": extra.get("video", "-"),
        "check": extra.get("check", row.get("next_lever", "-")),
        "evidence": extra.get("evidence", row.get("ledger", "-")),
    }


def status_rank(row: dict[str, str]) -> tuple[int, int, str]:
    order = {
        "submitted": 0,
        "active": 1,
        "ready-gate": 2,
        "blocked": 3,
        "ceiling": 4,
        "recon": 5,
        "scaffold": 6,
    }
    try:
        progress = -int(float(row.get("progress", "0") or 0))
    except Exception:
        progress = 0
    return (order.get(row.get("status", ""), 99), progress, row.get("key", ""))


def table(rows: list[dict[str, str]], cols: list[tuple[str, str]]) -> list[str]:
    out = ["| " + " | ".join(label for _, label in cols) + " |"]
    out.append("|" + "|".join("---" for _ in cols) + "|")
    for row in rows:
        out.append("| " + " | ".join(clip(row.get(key, "-"), 220).replace("|", "\\|") for key, _ in cols) + " |")
    return out


def main() -> None:
    check_only = "--check" in sys.argv[1:]
    registry_rows = read_registry()
    strict_mismatches = strict_status_audit(registry_rows)
    rows = [enrich(r) for r in registry_rows if r.get("status") in VISIBLE_STATUSES]
    rows.sort(key=status_rank)
    submitted = [r for r in rows if r["status"] == "submitted"]
    ev_rows = evidence_audit(submitted)
    ev_ok = sum(1 for e in ev_rows if e["verdict"].startswith("VERIFIED"))
    leaderboard_live = [
        r
        for r in rows
        if r["best"] != "-"
        and r["metric"] not in {"judged", "n/a", "none"}
        and r["key"] not in {x["key"] for x in submitted}
    ]
    operating = [r for r in rows if r["status"] in {"active", "ready-gate", "blocked"}]
    watch = [r for r in rows if r["status"] in {"ceiling", "recon", "scaffold"}]
    now = datetime.now().strftime("%Y-%m-%d %H:%M KST")

    md: list[str] = [
        "# Prizehunter Submission Board",
        "",
        f"_generated: {now}_",
        "",
        "Purpose: one human-readable place to see what is submitted, how to verify it, and what is still being operated. Sensitive lookup values are intentionally omitted.",
        "",
        "Operator confirmation runbook: `control_tower/SUBMISSION_CONFIRMATION_RUNBOOK.md`.",
        "",
        f"## Summary",
        "",
        f"- submitted: {len(submitted)}",
        f"- leaderboard/live score-tracked: {len(leaderboard_live)}",
        f"- operating now: {len(operating)}",
        f"- watch/scaffold/ceiling: {len(watch)}",
        f"- strict status mismatches: {len(strict_mismatches)}",
        f"- submitted evidence verified-on-disk: {ev_ok}/{len(ev_rows)}",
        "",
        "State definitions:",
        "",
        "- `submitted`: external portal/platform submission is recorded; monitor or edit only with a concrete reason.",
        "- `leaderboard/live score-tracked`: at least one scored submission or official/local scoring loop exists; keep chasing rank-1 if EV and transfer proof justify it.",
        "- `active`: agents can still build, validate, or package without a founder-only action.",
        "- `ready-gate`: materials are near-ready but external upload/account/identity/ToS/signature remains founder-gated.",
        "- `blocked`: a credential, eligibility, data-access, duplicate-entry, or platform gate stops progress until the route changes or founder clears it.",
        "- `ceiling`: submitted/scored work reached an honest ceiling; revive only with a materially new model/data/validation route.",
        "- `recon`/`scaffold`: discovered or prepared, not yet a committed submission loop.",
        "- `drop`: intentionally not in this board unless restored in `portfolio_registry.tsv`.",
        "",
        "## Submitted / Monitor",
        "",
    ]
    md += table(
        submitted,
        [
            ("key", "key"),
            ("name", "entry"),
            ("progress", "prog"),
            ("official", "official"),
            ("project", "project/check link"),
            ("repo", "repo"),
            ("demo", "demo"),
            ("video", "video"),
            ("check", "how to confirm"),
            ("evidence", "evidence"),
            ("next_lever", "next"),
        ],
    )
    md += [
        "",
        "## Submission Evidence Audit (on-disk)",
        "",
        "UNVERIFIED = 이 저장소에서 증거 파일/참조를 찾지 못했다는 뜻. 제출 여부의 단정이 아니라 \"증거 경로를 기록하라\"는 게이트 신호다 (Gmail/포털-측 증거도 유효 — Known Status Conflicts 참조).",
        "",
    ]
    md += table(ev_rows, [("key", "key"), ("verdict", "verdict"), ("found", "evidence found")])
    md += [
        "",
        "## Leaderboard Live / Score-Tracked",
        "",
        "These are not necessarily final portal submissions, but they do have live/local score state and must stay in the prize loop.",
        "",
    ]
    md += table(
        leaderboard_live,
        [
            ("key", "key"),
            ("name", "entry"),
            ("status", "status"),
            ("metric", "metric"),
            ("best", "best"),
            ("rank1", "rank1"),
            ("official", "official"),
            ("check", "how to confirm"),
            ("evidence", "evidence"),
            ("next_lever", "next"),
        ],
    )
    md += [
        "",
        "## Operating Now",
        "",
    ]
    md += table(
        operating,
        [
            ("key", "key"),
            ("status", "status"),
            ("progress", "prog"),
            ("best", "best"),
            ("rank1", "rank1"),
            ("blocker", "blocker"),
            ("next_lever", "next"),
        ],
    )
    md += [
        "",
        "## Watch / Ceiling / Scaffold",
        "",
    ]
    md += table(
        watch,
        [
            ("key", "key"),
            ("status", "status"),
            ("progress", "prog"),
            ("best", "best"),
            ("rank1", "rank1"),
            ("next_lever", "next"),
        ],
    )
    md += [
        "",
        "## Strict Status Audit",
        "",
    ]
    if strict_mismatches:
        md += table(
            strict_mismatches,
            [
                ("source", "source"),
                ("key", "key"),
                ("registry", "registry"),
                ("observed", "observed"),
                ("action", "action"),
            ],
        )
    else:
        md += ["No mismatches across strict generated status sources."]
    md += [
        "",
        "## Known Status Conflicts",
        "",
    ]
    md += table(
        KNOWN_STATUS_CONFLICTS,
        [
            ("key", "key"),
            ("current", "current authority"),
            ("conflict", "stale/conflicting source"),
            ("rule", "resolution rule"),
        ],
    )
    md += [
        "",
        "## Caveats",
        "",
        "- `portfolio_registry.tsv` is the status authority. Historical sale dossiers may contain stale states.",
        "- Devpost project URLs are recorded only when the project URL was captured. Otherwise use the Devpost manage page evidence.",
        "- MOCT lookup requires private founder fields; this board records the method but not the values.",
    ]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    fields = [
        "key",
        "status",
        "progress",
        "name",
        "official",
        "project",
        "repo",
        "demo",
        "video",
        "check",
        "evidence",
        "next_lever",
    ]
    with OUT_TSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, delimiter="\t", fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})

    print(OUT_MD)
    unverified = [e["key"] for e in ev_rows if e["verdict"].startswith("UNVERIFIED")]
    if check_only and unverified:
        # warning only (no exit-fail): absence of on-disk evidence must not be
        # escalated to a not-submitted claim — it is a record-the-evidence signal
        print(
            f"evidence warning: {len(unverified)} submitted row(s) without on-disk evidence: "
            + ", ".join(unverified),
            file=sys.stderr,
        )
    if check_only and strict_mismatches:
        for item in strict_mismatches:
            print(
                f"status mismatch: {item['source']} {item['key']} "
                f"observed={item['observed']} registry={item['registry']}",
                file=sys.stderr,
            )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
