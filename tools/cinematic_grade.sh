#!/usr/bin/env bash
# Non-destructive video color grade with raw/graded contact-sheet evidence.
set -euo pipefail

INPUT=""
OUTPUT=""
EVIDENCE_DIR=""
LOOK=""
CUSTOM_FILTER=""
LUT_PATH=""
INTERVAL_SECONDS="2"

usage() {
    cat <<'EOF'
Usage:
  cinematic_grade.sh --input RAW.mp4 --output GRADED.mp4 \
    --evidence-dir PATH --look cool_silver|teal_amber|warm_dusk|natural_contrast

  cinematic_grade.sh --input RAW.mp4 --output GRADED.mp4 \
    --evidence-dir PATH --look custom --filter 'ffmpeg video filter chain'

  cinematic_grade.sh --input RAW.mp4 --output GRADED.mp4 \
    --evidence-dir PATH --look lut --lut /absolute/look.cube

Raw input is never overwritten. Existing output/evidence files are refused.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --input) INPUT="${2:-}"; shift 2 ;;
        --output) OUTPUT="${2:-}"; shift 2 ;;
        --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
        --look) LOOK="${2:-}"; shift 2 ;;
        --filter) CUSTOM_FILTER="${2:-}"; shift 2 ;;
        --lut) LUT_PATH="${2:-}"; shift 2 ;;
        --interval-seconds) INTERVAL_SECONDS="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "error: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[[ -n "$INPUT" ]] || { echo "error: --input is required" >&2; exit 2; }
[[ -n "$OUTPUT" ]] || { echo "error: --output is required" >&2; exit 2; }
[[ -n "$EVIDENCE_DIR" ]] || { echo "error: --evidence-dir is required" >&2; exit 2; }
[[ -n "$LOOK" ]] || { echo "error: --look is required" >&2; exit 2; }
[[ -f "$INPUT" ]] || { echo "error: input not found: $INPUT" >&2; exit 2; }

INPUT_CANON="$(readlink -m "$INPUT")"
OUTPUT_CANON="$(readlink -m "$OUTPUT")"
[[ "$INPUT_CANON" != "$OUTPUT_CANON" ]] || {
    echo "error: refusing to overwrite raw input" >&2
    exit 2
}
[[ ! -e "$OUTPUT" ]] || { echo "error: output already exists: $OUTPUT" >&2; exit 2; }
[[ "$INTERVAL_SECONDS" =~ ^[0-9]+([.][0-9]+)?$ ]] || {
    echo "error: --interval-seconds must be numeric" >&2
    exit 2
}

if command -v ffmpeg >/dev/null 2>&1; then
    FFMPEG_BIN="$(command -v ffmpeg)"
else
    FFMPEG_BIN="$(
        python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'
    )"
fi
[[ -x "$FFMPEG_BIN" ]] || { echo "error: ffmpeg unavailable" >&2; exit 2; }

case "$LOOK" in
    cool_silver)
        VIDEO_FILTER='eq=contrast=1.16:brightness=-0.025:saturation=0.72:gamma=0.98,colorbalance=rs=-0.025:rm=-0.01:bs=0.08:bm=0.035:bh=0.02:pl=1,vignette=PI/7'
        ;;
    teal_amber)
        VIDEO_FILTER='eq=contrast=1.12:brightness=-0.015:saturation=0.88:gamma=0.99,colorbalance=rs=-0.035:bs=0.07:bm=0.035:rh=0.06:gh=0.02:pl=1,vignette=PI/8'
        ;;
    warm_dusk)
        VIDEO_FILTER='eq=contrast=1.10:brightness=-0.012:saturation=0.86:gamma=1.01,colorbalance=bs=-0.04:bm=-0.02:rh=0.08:gh=0.025:pl=1,vignette=PI/8'
        ;;
    natural_contrast)
        VIDEO_FILTER='eq=contrast=1.08:brightness=-0.008:saturation=0.92:gamma=1.00,vignette=PI/9'
        ;;
    custom)
        [[ -n "$CUSTOM_FILTER" ]] || {
            echo "error: --look custom requires --filter" >&2
            exit 2
        }
        VIDEO_FILTER="$CUSTOM_FILTER"
        ;;
    lut)
        [[ -n "$LUT_PATH" && -f "$LUT_PATH" ]] || {
            echo "error: --look lut requires an existing --lut file" >&2
            exit 2
        }
        VIDEO_FILTER="lut3d=file=$(readlink -m "$LUT_PATH")"
        ;;
    *)
        echo "error: unsupported look: $LOOK" >&2
        exit 2
        ;;
esac

RAW_SHEET="$EVIDENCE_DIR/raw_contact_sheet.png"
GRADED_SHEET="$EVIDENCE_DIR/graded_contact_sheet.png"
RECEIPT="$EVIDENCE_DIR/grade_receipt.md"
for evidence in "$RAW_SHEET" "$GRADED_SHEET" "$RECEIPT"; do
    [[ ! -e "$evidence" ]] || {
        echo "error: evidence already exists: $evidence" >&2
        exit 2
    }
done

mkdir -p "$(dirname "$OUTPUT")" "$EVIDENCE_DIR"

"$FFMPEG_BIN" -v error -i "$INPUT" -map 0:v:0 -f null -
"$FFMPEG_BIN" -hide_banner -loglevel error -i "$INPUT" \
    -map 0:v:0 -map 0:a? \
    -vf "$VIDEO_FILTER" \
    -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -movflags +faststart "$OUTPUT"
"$FFMPEG_BIN" -v error -i "$OUTPUT" -map 0:v:0 -f null -

SHEET_FILTER="fps=1/${INTERVAL_SECONDS},scale=480:-2,tile=4x1"
"$FFMPEG_BIN" -hide_banner -loglevel error -i "$INPUT" \
    -vf "$SHEET_FILTER" -frames:v 1 "$RAW_SHEET"
"$FFMPEG_BIN" -hide_banner -loglevel error -i "$OUTPUT" \
    -vf "$SHEET_FILTER" -frames:v 1 "$GRADED_SHEET"

RAW_SHA="$(sha256sum "$INPUT" | awk '{print $1}')"
GRADED_SHA="$(sha256sum "$OUTPUT" | awk '{print $1}')"
[[ "$RAW_SHA" != "$GRADED_SHA" ]] || {
    echo "error: graded output hash unexpectedly matches raw input" >&2
    exit 1
}
FFMPEG_VERSION="$("$FFMPEG_BIN" -version | sed -n '1p')"
TIMESTAMP="$(date --iso-8601=seconds)"

{
    echo "# Color Grade Receipt"
    echo
    echo "- Timestamp: \`$TIMESTAMP\`"
    echo "- Look: \`$LOOK\`"
    echo "- Raw input: \`$INPUT_CANON\`"
    echo "- Raw SHA-256: \`$RAW_SHA\`"
    echo "- Graded output: \`$OUTPUT_CANON\`"
    echo "- Graded SHA-256: \`$GRADED_SHA\`"
    echo "- Raw preserved: \`true\`"
    echo "- Decode validation: \`PASS\` for raw and graded video streams"
    echo "- Raw contact sheet: \`$(readlink -m "$RAW_SHEET")\`"
    echo "- Graded contact sheet: \`$(readlink -m "$GRADED_SHEET")\`"
    echo "- FFmpeg: \`$FFMPEG_VERSION\`"
    echo
    echo "## Applied video filter"
    echo
    echo '```text'
    echo "$VIDEO_FILTER"
    echo '```'
    echo
    echo "## Required human/vision QA"
    echo
    echo "- [ ] Palette remains inside the approved 2–3 dominant colors."
    echo "- [ ] Key-light direction and shadow source remain continuous."
    echo "- [ ] Declared time of day still reads correctly."
    echo "- [ ] Skin, brand, and factual colors remain acceptable where relevant."
    echo "- [ ] This shot matches both adjacent graded shots."
} > "$RECEIPT"

echo "PASS graded=$OUTPUT"
echo "PASS evidence=$EVIDENCE_DIR"
