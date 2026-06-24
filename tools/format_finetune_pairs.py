#!/usr/bin/env python3
"""
format_finetune_pairs.py — converts competition logs into LoRA instruction pairs
Output: $CT/sleep/training_pairs.jsonl  (ready for trl SFTTrainer)

Run by sleep_finetune.sh nightly. Also usable standalone:
  python3 format_finetune_pairs.py [--out PATH] [--min-pairs N]
"""
import re
import sys
import json
import argparse
from pathlib import Path

CT = Path(__file__).parent.parent

SYSTEM_PROMPT = (
    "You are prizehunter-instinct, an expert at winning AI/data competitions. "
    "Given a competition description, recommend the best approach based on past wins."
)


def extract_worklog_pairs(path: Path) -> list[dict]:
    """Pull (context, lesson) pairs from a WORKLOG.md file."""
    text = path.read_text(errors="replace")
    pairs = []

    # Pattern: competition metadata block
    meta = {}
    for m in re.finditer(r"- (domain|metric|prize|status):\s*(.+)", text):
        meta[m.group(1)] = m.group(2).strip()

    # Pattern: lines starting with a bullet that describe what worked
    for m in re.finditer(
        r"[-*]\s+([\w()·/\+→].{20,200}(?:게인|게인율|↑|→|works|proved|효과|유효|confirmed))",
        text,
        re.MULTILINE,
    ):
        lesson = m.group(1).strip()
        domain = meta.get("domain", "tabular")
        metric = meta.get("metric", "")
        instruction = (
            f"Competition domain: {domain}. Metric: {metric}. "
            f"Campaign: {path.parent.name}. What approach worked?"
        )
        pairs.append({
            "instruction": instruction,
            "output": lesson,
        })

    # Pattern: "next_lever" from registry (high-signal action)
    # ponytail: skipped complex NLP extraction — regex on bullet patterns is sufficient for this corpus size
    return pairs


def extract_corpus_pairs(path: Path) -> list[dict]:
    """Pull pairs from CORPUS_REPORT.md."""
    text = path.read_text(errors="replace")
    pairs = []
    sections = re.split(r"^#+\s+", text, flags=re.MULTILINE)
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue
        header = lines[0]
        body = "\n".join(lines[1:]).strip()
        if len(body) < 30:
            continue
        if any(kw in header.lower() for kw in ["pattern", "lesson", "win", "approach", "이슈"]):
            pairs.append({
                "instruction": f"Competition insight category: {header}. What was learned?",
                "output": body[:500],
            })
    return pairs


def to_chat_format(pair: dict) -> dict:
    """Convert to messages format for SFTTrainer."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": pair["instruction"]},
            {"role": "assistant", "content": pair["output"]},
        ]
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(CT / "sleep" / "training_pairs.jsonl"))
    ap.add_argument("--min-pairs", type=int, default=5)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    pairs = []

    # Corpus report
    corpus = CT / "session_corpus" / "CORPUS_REPORT.md"
    if corpus.exists():
        pairs += extract_corpus_pairs(corpus)

    # All campaign worklogs
    for wl_name in ("WORKLOG.md", "AGENT_WORKLOG.md", "RECON.md"):
        for wl in (CT / "campaigns").rglob(wl_name):
            pairs += extract_worklog_pairs(wl)

    if len(pairs) < args.min_pairs:
        print(f"⚠ Only {len(pairs)} pairs extracted — corpus too thin for finetune. Run mine_sessions.py first.")
        sys.exit(0)

    with open(out, "w") as f:
        for p in pairs:
            f.write(json.dumps(to_chat_format(p), ensure_ascii=False) + "\n")

    print(f"✓ {len(pairs)} training pairs → {out}")


if __name__ == "__main__":
    main()
