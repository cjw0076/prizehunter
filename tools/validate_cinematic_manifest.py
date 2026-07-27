#!/usr/bin/env python3
"""Validate the mandatory cinematic fields in competition video manifests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_LIGHTING = (
    "key_direction",
    "key_type",
    "key_color_temperature_k",
    "key_hardness",
    "ambient_fill",
    "rim_or_backlight",
    "contrast_ratio",
    "shadow_intent",
)
REQUIRED_CAMERA = ("lens", "motion", "stability")
REQUIRED_GRADE = (
    "look",
    "raw_clip_path",
    "graded_clip_path",
    "before_after_evidence_path",
)


def nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def require_fields(
    obj: Any, fields: tuple[str, ...], prefix: str, errors: list[str]
) -> None:
    if not isinstance(obj, dict):
        errors.append(f"{prefix}: expected object")
        return
    for field in fields:
        if field not in obj or not nonempty(obj[field]):
            errors.append(f"{prefix}.{field}: missing or empty")


def validate_palette(
    palette: Any, prefix: str, errors: list[str]
) -> list[str]:
    if not isinstance(palette, dict):
        errors.append(f"{prefix}: expected object")
        return []
    colors = palette.get("primary_colors")
    if not isinstance(colors, list) or not 2 <= len(colors) <= 3:
        errors.append(f"{prefix}.primary_colors: require exactly 2 or 3 colors")
        return []
    normalized = [str(color).strip() for color in colors]
    if any(not color for color in normalized):
        errors.append(f"{prefix}.primary_colors: colors must be non-empty strings")
    if len({color.casefold() for color in normalized}) != len(normalized):
        errors.append(f"{prefix}.primary_colors: colors must be unique")
    forbidden = palette.get("forbidden_colors")
    if not isinstance(forbidden, list):
        errors.append(f"{prefix}.forbidden_colors: require an array")
    return normalized


def shot_id(shot: dict[str, Any], index: int) -> str:
    return str(shot.get("id") or shot.get("shot") or f"shots[{index}]")


def validate_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: cannot read valid JSON: {exc}"]

    if not isinstance(data, dict):
        return [f"{path}: root must be an object"]

    bible = data.get("cinematic_look_bible")
    if not isinstance(bible, dict):
        return [f"{path}: cinematic_look_bible is required"]

    film_colors = validate_palette(
        bible.get("palette"), "cinematic_look_bible.palette", errors
    )
    if not nonempty(bible.get("lighting_continuity")):
        errors.append("cinematic_look_bible.lighting_continuity: missing or empty")

    grade = bible.get("grade")
    require_fields(
        grade,
        (
            "tool_chain",
            "creative_look",
            "raw_master_preserved",
            "graded_master_path",
            "before_after_evidence_path",
        ),
        "cinematic_look_bible.grade",
        errors,
    )
    if isinstance(grade, dict) and grade.get("raw_master_preserved") is not True:
        errors.append(
            "cinematic_look_bible.grade.raw_master_preserved: must be true"
        )

    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("shots: require a non-empty array")
        return errors

    film_set = {color.casefold() for color in film_colors}
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            errors.append(f"shots[{index}]: expected object")
            continue
        sid = shot_id(shot, index)
        prefix = f"shot[{sid}].cinematic"
        cinematic = shot.get("cinematic")
        if not isinstance(cinematic, dict):
            errors.append(f"{prefix}: required object")
            continue

        require_fields(
            cinematic.get("time_of_day"),
            ("exact_local_time", "phase", "weather"),
            f"{prefix}.time_of_day",
            errors,
        )
        require_fields(
            cinematic.get("lighting"),
            REQUIRED_LIGHTING,
            f"{prefix}.lighting",
            errors,
        )
        shot_colors = validate_palette(
            cinematic.get("palette"), f"{prefix}.palette", errors
        )
        for color in shot_colors:
            if film_set and color.casefold() not in film_set:
                errors.append(
                    f"{prefix}.palette.primary_colors: {color!r} is outside film palette"
                )

        require_fields(
            cinematic.get("camera"),
            REQUIRED_CAMERA,
            f"{prefix}.camera",
            errors,
        )
        post_grade = cinematic.get("post_grade")
        require_fields(
            post_grade,
            REQUIRED_GRADE,
            f"{prefix}.post_grade",
            errors,
        )
        if isinstance(post_grade, dict):
            raw_path = post_grade.get("raw_clip_path")
            graded_path = post_grade.get("graded_clip_path")
            if nonempty(raw_path) and raw_path == graded_path:
                errors.append(
                    f"{prefix}.post_grade: raw and graded paths must differ"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="+", type=Path)
    args = parser.parse_args()

    failed = False
    for path in args.manifests:
        errors = validate_manifest(path)
        if errors:
            failed = True
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
