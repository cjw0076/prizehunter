#!/usr/bin/env python3
"""Prepare Higgsfield/Seedance production queues for video campaigns."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CT = ROOT / "competitions" / "control_tower"
REGISTRY = CT / "portfolio_registry.tsv"

VIDEO_HINTS = ("video", "film", "gamff", "kai", "quiznos", "racing")
SOURCE_DOCS = (
    "STORYBOARD.md",
    "PRODUCTION_GUIDE.md",
    "CREATIVE_DIRECTOR_BRIEF.md",
    "SUBMIT_NOW.md",
    "CAMPAIGN.md",
    "RECON.md",
)


def kst_now() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%dT%H:%M:%S%z")


def read_registry() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with REGISTRY.open(newline="", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            rows.extend(csv.DictReader([line] + list(f), delimiter="\t"))
            break
    return rows


def is_video_campaign(row: dict[str, str]) -> bool:
    haystack = " ".join(
        row.get(k, "") for k in ("key", "dir", "ledger", "blocker", "next_lever")
    ).lower()
    return any(hint in haystack for hint in VIDEO_HINTS)


def campaign_dir(row: dict[str, str]) -> Path:
    return ROOT / row["dir"]


def read_source_bundle(cdir: Path) -> tuple[list[str], str]:
    found: list[str] = []
    chunks: list[str] = []
    for name in SOURCE_DOCS:
        path = cdir / name
        if path.exists():
            found.append(name)
            text = path.read_text(encoding="utf-8", errors="replace")
            chunks.append(f"\n\n## {name}\n\n{text[:12000]}")
    return found, "".join(chunks)


def primary_scene_source(cdir: Path) -> str:
    """Use one scene-bearing source to avoid duplicate queues across copied docs."""
    fallback: list[str] = []
    for name in SOURCE_DOCS:
        path = cdir / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fallback.append(text[:12000])
        if re.search(r"(?im)^#{2,4}\s*(?:씬|scene)\s*[0-9]+", text):
            return text[:12000]
    return "\n\n".join(fallback)


def extract_scenes(bundle: str) -> list[dict[str, str]]:
    matches = list(
        re.finditer(
            r"(?im)^#{2,4}\s*(?:씬|scene)\s*([0-9]+)\s*(?:[—:-]\s*)?(.+)$",
            bundle,
        )
    )
    scenes: list[dict[str, str]] = []
    if matches:
        for idx, match in enumerate(matches, 1):
            start = match.end()
            end = matches[idx].start() if idx < len(matches) else len(bundle)
            body = bundle[start:end].strip()
            title = match.group(2).strip()
            scenes.append(
                {
                    "id": f"scene_{idx:02d}",
                    "title": title[:120],
                    "source_excerpt": body[:1800],
                }
            )
    if not scenes:
        scenes = [
            {
                "id": f"scene_{idx:02d}",
                "title": f"Scene {idx}",
                "source_excerpt": "Fill from storyboard or production guide.",
            }
            for idx in range(1, 6)
        ]
    return scenes[:12]


def infer_specs(bundle: str) -> dict[str, str]:
    aspect = "16:9"
    if re.search(r"(?i)9:16|vertical|short-form|숏폼|세로", bundle):
        aspect = "9:16"
    duration = "contest-specific"
    m = re.search(r"(?i)(총\s*)?([0-9]{2,3})\s*(초|seconds|sec)", bundle)
    if m:
        duration = f"{m.group(2)} seconds"
    return {
        "aspect_ratio": aspect,
        "target_duration": duration,
        "draft_model": "Higgsfield Seedance low/cost model",
        "final_model": "Higgsfield Seedance 2.0+",
    }


def source_image_prompt(key: str, scene: dict[str, str]) -> str:
    excerpt = scene["source_excerpt"].strip()[:1200].replace("```", "'''")
    return f"""### {scene['id']} — {scene['title']}

Generate source/key images before video:

1. Character/world board still
   - Use Gemini image generation or ChatGPT image generation.
   - Preserve exact local/cultural details from the source excerpt.
   - No fake Korean text unless the submission requires text.

2. Key frame still
   - Cinematic production still for the start frame.
   - Clear subject, readable composition, stable lighting, no generic AI glow.

3. End frame still
   - The intended final frame for image-to-video continuity.

Source excerpt:
```text
{excerpt}
```

Negative prompt:
generic hologram UI, glowing orb, fake unreadable Korean text, warped logos,
extra fingers, melted faces, wrong landmark, stock-photo composition
"""


def write_campaign(row: dict[str, str]) -> dict[str, str]:
    key = row["key"]
    cdir = campaign_dir(row)
    cdir.mkdir(parents=True, exist_ok=True)
    assets = cdir / "video_assets"
    assets.mkdir(exist_ok=True)
    found, bundle = read_source_bundle(cdir)
    scene_source = primary_scene_source(cdir)
    scenes = extract_scenes(scene_source)
    specs = infer_specs(bundle)
    generated_at = kst_now()

    queue = {
        "pipeline_version": "higgsfield_seedance_v1",
        "generated_at_kst": generated_at,
        "campaign_key": key,
        "campaign_dir": str(cdir.relative_to(ROOT)),
        "source_docs": found,
        "status": "source_image_prompt_ready",
        "tools": {
            "source_images": ["gemini.google.ai", "chatgpt.com image generation"],
            "vibe_video": specs["draft_model"],
            "final_video": specs["final_model"],
            "editing": ["CapCut", "Premiere", "DaVinci Resolve"],
        },
        "gates": [
            {
                "name": "source_images_ready",
                "required_before": "low_cost_seedance_vibe_check",
                "evidence": "video_assets/source_image_manifest.tsv",
            },
            {
                "name": "low_cost_vibe_passed",
                "required_before": "seedance_2_plus_generation",
                "evidence": "video_assets/vibe_check_scorecard.md",
            },
            {
                "name": "edit_export_verified",
                "required_before": "external_submission",
                "evidence": "video_assets/final_export_receipt.md",
            },
        ],
        "specs": specs,
        "scenes": [
            {
                "id": s["id"],
                "title": s["title"],
                "source_images": [],
                "draft_videos": [],
                "final_videos": [],
                "vibe_status": "pending",
            }
            for s in scenes
        ],
    }

    (assets / "higgsfield_seedance_queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    prompts = [
        f"# Source Image Prompts — {key}",
        "",
        f"Generated: {generated_at} KST",
        "",
        "Use Gemini image generation or ChatGPT image generation to create the",
        "character board, world board, start frame, and end frame before any video",
        "generation. Save outputs in this folder and record filenames in",
        "`source_image_manifest.tsv`.",
        "",
    ]
    prompts.extend(source_image_prompt(key, scene) for scene in scenes)
    (assets / "SOURCE_IMAGE_PROMPTS.md").write_text("\n".join(prompts), encoding="utf-8")

    scorecard = f"""# Vibe Check Scorecard — {key}

Generated: {generated_at} KST

## Rule

Run the cheap Higgsfield Seedance draft first. Seedance 2.0+ is allowed only
after every final scene candidate scores at least 4/5 on theme fit and 4/5 on
visual continuity.

| scene | source image file | low-model asset id | theme fit 1-5 | motion 1-5 | continuity 1-5 | cliche risk 1-5 low=good | decision | notes |
|---|---|---|---:|---:|---:|---:|---|---|
"""
    for scene in scenes:
        scorecard += f"| {scene['id']} | TBD | TBD | 0 | 0 | 0 | 0 | pending | {scene['title']} |\n"
    scorecard += """
## High-Model Approval

- [ ] All source images recorded in `source_image_manifest.tsv`
- [ ] Low-cost drafts reviewed by at least one critic agent or human
- [ ] No generic AI-glow fallback remains
- [ ] Final model, seed, cost, and asset IDs will be recorded before editing
"""
    (assets / "vibe_check_scorecard.md").write_text(scorecard, encoding="utf-8")

    manifest = assets / "source_image_manifest.tsv"
    if not manifest.exists():
        manifest.write_text(
            "scene\trole\ttool\tprompt_file\toutput_file\tseed_or_id\tlicense_note\tqa_status\n",
            encoding="utf-8",
        )

    pipeline = f"""# Video Production Pipeline — {key}

Generated: {generated_at} KST

This campaign now follows the control-tower Higgsfield/Seedance production
standard:

1. Claude/storyboard source is treated as the creative base.
2. Gemini or ChatGPT image generation creates character/world/key-frame boards.
3. Higgsfield Seedance low/cost model checks vibe and continuity.
4. Seedance 2.0+ produces final clips only after the vibe gate passes.
5. Editing/export/submission evidence is recorded before closeout.

## Current Inputs

- Campaign dir: `{cdir.relative_to(ROOT)}`
- Source docs found: {", ".join(found) if found else "none yet"}
- Aspect ratio: {specs["aspect_ratio"]}
- Target duration: {specs["target_duration"]}
- Existing blocker: {row.get("blocker", "-")}

## Control Files

- `video_assets/SOURCE_IMAGE_PROMPTS.md`
- `video_assets/source_image_manifest.tsv`
- `video_assets/higgsfield_seedance_queue.json`
- `video_assets/vibe_check_scorecard.md`

## Next Action

Generate the source images first, then fill `source_image_manifest.tsv`.
After that, run low-cost Higgsfield/Seedance drafts and score them in
`vibe_check_scorecard.md`. Do not run Seedance 2.0+ until the scorecard passes.

## Submission Boundary

External upload/account/ToS remains founder-gated unless this campaign has a
separate written automation exception. Agents may prepare the upload package,
copy, final MP4 path, screenshots, and evidence checklist.
"""
    (cdir / "VIDEO_PRODUCTION_PIPELINE.md").write_text(pipeline, encoding="utf-8")

    return {"key": key, "dir": str(cdir.relative_to(ROOT)), "scenes": str(len(scenes))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("key", nargs="?", help="campaign key; omit with --all")
    parser.add_argument("--all", action="store_true", help="refresh every active video campaign")
    args = parser.parse_args()

    rows = read_registry()
    if args.all:
        targets = [r for r in rows if is_video_campaign(r) and r.get("status") != "submitted"]
    else:
        if not args.key:
            parser.error("provide <key> or --all")
        targets = [r for r in rows if r.get("key") == args.key]
        if not targets:
            # Allow direct folder names for materialized campaigns not yet in registry.
            cdir = CT / "campaigns" / args.key
            if not cdir.exists():
                raise SystemExit(f"unknown campaign key: {args.key}")
            targets = [
                {
                    "key": args.key,
                    "dir": str(cdir.relative_to(ROOT)),
                    "blocker": "-",
                    "status": "active",
                }
            ]

    results = [write_campaign(row) for row in targets]

    report = CT / "VIDEO_PIPELINE_REPORT.md"
    lines = [
        "# Video Pipeline Report",
        "",
        f"Generated: {kst_now()} KST",
        "",
        "| key | dir | scenes queued |",
        "|---|---|---:|",
    ]
    for r in results:
        lines.append(f"| {r['key']} | `{r['dir']}` | {r['scenes']} |")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"prepared {len(results)} video campaign(s)")
    print(f"report: {report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
