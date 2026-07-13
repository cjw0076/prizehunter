#!/usr/bin/env python3
"""Founder/auth gate dashboard for prizehunter.

The submission board shows what exists. This dashboard shows what the operator
needs to do next: auth, account, ToS, signature, final upload, spend, or real
walkthrough gates. It must never print credential values.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
ROOT = CONTROL.parents[1]
REGISTRY = CONTROL / "portfolio_registry.tsv"
QUALITY_TSV = CONTROL / "QUALITY_GATE_REPORT.tsv"
OUT_MD = CONTROL / "FOUNDER_AUTH_DASHBOARD.md"
OUT_TSV = CONTROL / "FOUNDER_AUTH_DASHBOARD.tsv"


AUTH_RE = re.compile(
    r"auth|api[_ -]?key|token|credential|login|logged|session|whest login|"
    r"aicrowd|zindi|kaggle|crunch|hf_token|authenticated|인증|로그인",
    re.I,
)
LEGAL_RE = re.compile(
    r"tos|rules|official rules|warranty|signature|sign|identity|consent|"
    r"terms|개인|서명|동의|약관|규칙|신원|본인",
    re.I,
)
SUBMIT_RE = re.compile(
    r"submit|upload|portal|form|final|registration|account|team|apply|"
    r"제출|업로드|접수|신청|가입|계정|팀",
    re.I,
)
SPEND_RE = re.compile(r"spend|payment|pay|wallet|usdc|billing|fee|결제|지갑|비용", re.I)
VALIDATION_RE = re.compile(r"walkthrough|operator|validation|review/use|검증|사용자|운영자", re.I)
EXPLICIT_GATE_RE = re.compile(
    r"FOUNDER|DELEGATED GATE|Credential gate|founder-gate|auth|api[_ -]?key|token|"
    r"login|signup|join|registration|account|ToS|rules-acceptance|spend|wallet|"
    r"참가신청|가입|로그인|인증|계정|접수|신청|결제|지갑|서명|동의",
    re.I,
)


# Empty in the shipped product. Per-competition operator instructions are read
# from the registry instead: put a `FOUNDER:`-prefixed note in a row's `blocker`
# or `next_lever` and it flows through as the request / retry_or_operator_action
# (see build_rows). Add entries here only to pin a custom retry command per key.
KNOWN_RETRY: dict[str, str] = {}


def now_kst() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M KST")


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="ignore", newline="") as f:
        lines = (
            line
            for line in f
            if line.strip() and not line.lstrip().lstrip('"').startswith("#")
        )
        return [{k: (v or "") for k, v in row.items()} for row in csv.DictReader(lines, delimiter="\t")]


def clean(text: str, max_len: int = 260) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    text = text.replace("|", "\\|")
    return text if len(text) <= max_len else text[: max_len - 3].rstrip() + "..."


def gate_class(text: str) -> str:
    classes: list[str] = []
    if AUTH_RE.search(text):
        classes.append("AUTH")
    if LEGAL_RE.search(text):
        classes.append("LEGAL/TOS")
    if SPEND_RE.search(text):
        classes.append("SPEND")
    if SUBMIT_RE.search(text):
        classes.append("SUBMIT/ACCOUNT")
    if VALIDATION_RE.search(text):
        classes.append("OPERATOR_VALIDATION")
    if not classes:
        classes.append("FOUNDER_ACTION")
    return "+".join(classes)


def is_gate(row: dict[str, str], quality: dict[str, dict[str, str]]) -> bool:
    key = row.get("key", "")
    q = quality.get(key, {})
    status = row.get("status", "")
    text = " ".join(
        [
            status,
            row.get("blocker", ""),
            row.get("next_lever", ""),
            q.get("top_findings", ""),
            q.get("next_gate", ""),
        ]
    )
    if status in {"submitted", "drop", "ceiling"}:
        return False
    if status in {"blocked", "ready-gate"}:
        return True
    if status in {"recon", "scaffold"}:
        return bool(EXPLICIT_GATE_RE.search(text))
    return bool(AUTH_RE.search(text) or LEGAL_RE.search(text) or SUBMIT_RE.search(text) or VALIDATION_RE.search(text) or SPEND_RE.search(text))


def priority(row: dict[str, str], q: dict[str, str], cls: str) -> int:
    status_weight = {
        "blocked": 100,
        "ready-gate": 90,
        "active": 70,
        "recon": 35,
        "scaffold": 25,
        "submitted": 10,
        "drop": 0,
        "ceiling": 0,
    }.get(row.get("status", ""), 30)
    win = int(float(q.get("win_probability") or 0))
    progress = int(float(row.get("progress") or 0))
    cls_weight = 0
    if "AUTH" in cls:
        cls_weight += 12
    if "SUBMIT" in cls:
        cls_weight += 8
    if "OPERATOR_VALIDATION" in cls:
        cls_weight += 6
    if "SPEND" in cls:
        cls_weight -= 25
    if row.get("status") == "submitted":
        cls_weight -= 60
    return status_weight + win + progress // 3 + cls_weight


def build_rows() -> list[dict[str, str]]:
    registry = read_tsv(REGISTRY)
    quality_rows = read_tsv(QUALITY_TSV)
    quality = {r.get("key", ""): r for r in quality_rows}
    out: list[dict[str, str]] = []

    for row in registry:
        key = row.get("key", "")
        q = quality.get(key, {})
        if not key or not is_gate(row, quality):
            continue
        text = " ".join([row.get("blocker", ""), row.get("next_lever", ""), q.get("next_gate", "")])
        cls = gate_class(text)
        request = q.get("next_gate") or row.get("next_lever") or row.get("blocker")
        out.append(
            {
                "priority": str(priority(row, q, cls)),
                "key": key,
                "class": cls,
                "status": row.get("status", ""),
                "progress": row.get("progress", ""),
                "win_probability": q.get("win_probability", ""),
                "request": clean(request, 360),
                "safe_agent_work": clean(_safe_agent_work(key, row, q), 320),
                "retry_or_operator_action": clean(KNOWN_RETRY.get(key, request), 420),
                "evidence": clean(row.get("ledger", ""), 220),
            }
        )

    out.sort(key=lambda r: int(r["priority"]), reverse=True)
    return out


def _safe_agent_work(key: str, row: dict[str, str], q: dict[str, str]) -> str:
    if row.get("status") == "blocked":
        return "Record exact gate class and work another contest unless credentials/session are available."
    return q.get("strategy_gaps") or "Prepare package/checklists; leave irreversible action to founder/auth gate."


def write(rows: list[dict[str, str]]) -> None:
    with OUT_TSV.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "priority",
            "key",
            "class",
            "status",
            "progress",
            "win_probability",
            "request",
            "safe_agent_work",
            "retry_or_operator_action",
            "evidence",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    lines: list[str] = []
    lines.append("# Founder/Auth Gate Dashboard")
    lines.append("")
    lines.append(f"_generated: {now_kst()}_")
    lines.append("")
    lines.append("Purpose: one place for the operator to see which auth, account, ToS, upload, signature, spend, or real-user validation gates block prizehunter. Secrets are never shown.")
    lines.append("")
    lines.append(f"- open gates: {len(rows)}")
    lines.append(f"- auth-related: {sum('AUTH' in r['class'] for r in rows)}")
    lines.append(f"- submit/account-related: {sum('SUBMIT' in r['class'] for r in rows)}")
    lines.append(f"- spend-related: {sum('SPEND' in r['class'] for r in rows)}")
    lines.append("")
    lines.append("## Operator Queue")
    lines.append("")
    lines.append("| priority | key | class | status | prog | win% | request | safe agent work | retry/operator action | evidence |")
    lines.append("|---:|---|---|---|---:|---:|---|---|---|---|")
    for r in rows:
        lines.append(
            "| {priority} | {key} | {class} | {status} | {progress} | {win_probability} | {request} | {safe_agent_work} | {retry_or_operator_action} | {evidence} |".format(
                **r
            )
        )
    lines.append("")
    lines.append("## Rules")
    lines.append("")
    lines.append("- Do not paste secrets into chat, docs, receipts, Notion, or git.")
    lines.append("- For API keys, prefer a local login command or environment variable visible only to the shell.")
    lines.append("- Legal/ToS/signature/payment/identity actions remain operator-gated unless a contest-specific standing delegation receipt exists.")
    lines.append("- After clearing a gate, run `ph gates`, then the listed retry command, then `ph submitted --check` and `ph tick`.")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows = build_rows()
    write(rows)
    print(OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
