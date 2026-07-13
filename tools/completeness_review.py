#!/usr/bin/env python3
"""Package completeness review for prizehunter campaigns.

This complements quality_gate.py:
- quality_gate.py estimates EV, lane fit, and strategy gaps.
- completeness_review.py checks whether the current package has enough
  judge-facing evidence to survive a serious pre-submit review.
"""
from __future__ import annotations

import argparse
import csv
import re
import zipfile
from datetime import datetime
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
ROOT = CONTROL.parents[1]
REGISTRY = CONTROL / "portfolio_registry.tsv"
PACKAGES = CONTROL / "EXIT" / "packages"
OUT_MD = CONTROL / "COMPLETENESS_REVIEW.md"
OUT_TSV = CONTROL / "COMPLETENESS_REVIEW.tsv"

FOUNDER_RE = re.compile(
    r"FOUNDER:|ToS|final submit|final portal|login|account|spend|written confirmation|"
    r"founder handles|external upload|외부 제출|최종 제출|서명|날인|본인인증",
    re.I,
)

CHECKS = {
    "universal": [
        ("official rules captured", [r"official.*rules?", r"contest rules", r"공모요강", r"OFFICIAL"], [r"OFFICIAL", r"RULE"]),
        ("deliverable manifest", [r"manifest", r"submission guide", r"제출 가이드"], [r"MANIFEST", r"SUBMISSION_GUIDE"]),
        ("founder gate explicit", [r"founder", r"ToS", r"external upload", r"서명", r"본인인증"], [r"FOUNDER", r"SUBMISSION_GUIDE"]),
        ("rights/privacy risk checked", [r"rights", r"license", r"privacy", r"저작권", r"개인정보"], [r"RIGHT", r"RISK", r"POLICY"]),
        ("no obvious placeholders", [], []),
    ],
    "idea_design": [
        ("clear problem and user", [r"problem", r"user", r"operator", r"stakeholder", r"senior", r"pharmac"], []),
        ("specific solution mechanics", [r"workflow", r"architecture", r"prototype", r"diagram"], [r"\.png$", r"illustration"]),
        ("implementation / adoption plan", [r"deployment", r"market entry", r"adoption", r"cost", r"budget"], []),
        ("impact and risk argument", [r"impact", r"risk", r"public good", r"safety"], [r"RISK"]),
    ],
    "publicdata_product": [
        ("data provenance", [r"source", r"provenance", r"data\.go\.kr", r"공공데이터"], [r"data", r"source"]),
        ("runnable artifact", [r"runnable", r"demo", r"prototype"], [r"index\.html", r"\.py$"]),
        ("methodology / impact math", [r"methodology", r"impact", r"savings", r"benefit"], []),
        ("real validation", [r"walkthrough", r"operator validation", r"user validation"], [r"walkthrough"]),
    ],
    "leaderboard": [
        ("CV or OOF evidence", [r"\bcv\b", r"\boof\b", r"cross[- ]?validation"], []),
        ("ablation or error analysis", [r"ablation", r"error", r"실험", r"오류"], []),
        ("submission economy rule", [r"submit", r"overfit", r"luck", r"ceiling"], []),
    ],
    "hackathon": [
        ("repo and license", [r"github", r"repo", r"license"], []),
        ("hosted/runnable demo", [r"hosted", r"demo", r"live"], [r"index\.html"]),
        ("video/deck/story", [r"video", r"deck", r"slides", r"storyboard"], []),
    ],
    "creative_media": [
        ("final visual/media", [r"final", r"storyboard", r"visual"], [r"\.png$", r"\.jpg$", r"\.mp4$", r"\.mov$"]),
        ("rights/AI-use policy", [r"rights", r"license", r"ai use", r"저작권"], []),
        ("variants or critique", [r"variant", r"critique", r"review"], []),
    ],
}

LANE_PATTERNS = {
    "leaderboard": r"kaggle|dacon|leaderboard|accuracy|logloss|nmae|알고리즘|예측",
    "hackathon": r"hackathon|devpost|앱|웹|sw|software",
    "publicdata_product": r"공공데이터|data\.go\.kr|제품|서비스|산업통상|부산",
    "creative_media": r"영상|ucc|film|media|디자인|웹툰|포스터|광고|art|창작",
    "idea_design": r"아이디어|기획|invention|design|제안|future|techbriefs",
}

# Empty in the shipped product: lanes are inferred from LANE_PATTERNS against the
# registry row (see lane_for). Add your own keys here only to pin a lane, e.g.
# LANE_OVERRIDES = {"example-comp": "leaderboard"}.
LANE_OVERRIDES: dict[str, str] = {}


def read_registry() -> list[dict[str, str]]:
    if not REGISTRY.exists():
        return []
    with REGISTRY.open(encoding="utf-8", errors="ignore") as f:
        return list(csv.DictReader((line for line in f if line.strip() and not line.startswith("#")), delimiter="\t"))


def lane_for(row: dict[str, str]) -> str:
    if row.get("key") in LANE_OVERRIDES:
        return LANE_OVERRIDES[row.get("key", "")]
    blob = " ".join(row.get(k, "") for k in row).lower()
    for lane, pat in LANE_PATTERNS.items():
        if re.search(pat, blob, flags=re.I):
            return lane
    return "other"


def latest_package(key: str) -> Path | None:
    files = sorted(PACKAGES.glob(f"{key}_submission_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def zip_entries(pkg: Path | None) -> list[str]:
    if not pkg:
        return []
    try:
        with zipfile.ZipFile(pkg) as zf:
            return zf.namelist()
    except Exception:
        return []


def sample_text(campdir: Path) -> str:
    chunks: list[str] = []
    package_dir = campdir / "submission_package"
    patterns = ["submission_package/*.md"] if package_dir.exists() else ["*.md", "deliverables/*.md"]
    for pat in patterns:
        for path in sorted(campdir.glob(pat))[:80]:
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore")[:6000])
            except Exception:
                pass
    return "\n".join(chunks)


def has_entry(entries: list[str], patterns: list[str]) -> bool:
    return any(re.search(p, entry, flags=re.I) for entry in entries for p in patterns)


def check_item(label: str, text_patterns: list[str], entry_patterns: list[str], text: str, entries: list[str]) -> tuple[bool, str]:
    if label == "no obvious placeholders":
        bad = re.search(r"\bTODO\b|TBD|fill:|placeholder|lorem|\.{3,}|intentionally blank", text, flags=re.I)
        return (not bad), "placeholder scan"
    text_ok = any(re.search(p, text, flags=re.I) for p in text_patterns)
    entry_ok = has_entry(entries, entry_patterns) if entry_patterns else False
    return text_ok or entry_ok, "text/package evidence"


def review_row(row: dict[str, str]) -> dict[str, str]:
    key = row.get("key", "")
    campdir = ROOT / row.get("dir", "")
    lane = lane_for(row)
    pkg = latest_package(key)
    entries = zip_entries(pkg)
    text = sample_text(campdir)
    checks = CHECKS["universal"] + CHECKS.get(lane, CHECKS["idea_design"])
    passed: list[str] = []
    failed: list[str] = []
    for label, text_patterns, entry_patterns in checks:
        ok, _ = check_item(label, text_patterns, entry_patterns, text, entries)
        (passed if ok else failed).append(label)
    score = round(100 * len(passed) / max(1, len(checks)))
    if not pkg:
        failed.insert(0, "local zip package")
        score = max(0, score - 20)
    if FOUNDER_RE.search((row.get("blocker", "") + " " + row.get("next_lever", ""))):
        failed.append("external founder gate remains")
        score = min(score, 84)
    status = "ready-gate" if score >= 80 and "external founder gate remains" in failed else "agent-polish" if score >= 60 else "incomplete"
    return {
        "key": key,
        "lane": lane,
        "registry_status": row.get("status", ""),
        "score": str(score),
        "review_status": status,
        "package": str(pkg.relative_to(ROOT)) if pkg else "-",
        "passed": "; ".join(passed) or "-",
        "failed": "; ".join(failed) or "-",
        "next": "Founder handles external gate after final human review." if status == "ready-gate" else "Fix failed completeness checks before more polish/submission.",
    }


def write(rows: list[dict[str, str]]) -> None:
    cols = ["key", "lane", "registry_status", "score", "review_status", "package", "failed", "next"]
    with OUT_TSV.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(r[c].replace("\n", " ") for c in cols) + "\n")
    with OUT_MD.open("w", encoding="utf-8") as f:
        f.write("# Completeness Review\n\n")
        f.write(f"- generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}\n")
        f.write("- purpose: catch shallow/fast packages before founder-gated submission\n")
        f.write("- rule: a high score is not permission to submit; external upload, ToS, identity, spend, and signatures remain founder-only\n\n")
        f.write("| score | status | lane | key | failed checks | next |\n")
        f.write("|---:|---|---|---|---|---|\n")
        for r in rows:
            if r["registry_status"] in {"active", "ready-gate", "submitted", "blocked", "ceiling"}:
                f.write(f"| {r['score']} | {r['review_status']} | {r['lane']} | `{r['key']}` | {r['failed']} | {r['next']} |\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", help="review one competition key")
    args = parser.parse_args()
    rows = [review_row(r) for r in read_registry() if r.get("key") and (not args.key or r.get("key") == args.key)]
    rows.sort(key=lambda r: int(r["score"]), reverse=True)
    write(rows)
    print(OUT_MD)
    print(OUT_TSV)
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
