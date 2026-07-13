#!/usr/bin/env bash
# visual_confirm.sh — Codex-owned visual QA for prizehunter submissions.
set -euo pipefail

CONTROL="$(cd -- "$(dirname "$0")/.." && pwd)"
ROOT="$(cd -- "$CONTROL/../.." && pwd)"
OUT="$CONTROL/EXIT/VISUAL_CONFIRMATION.md"
VIS="$CONTROL/EXIT/visuals"

mkdir -p "$VIS"

cat >"$OUT" <<'EOF'
# Visual Confirmation — Codex QA

Codex owns final visual confirmation before a competition package is treated as
submission-polished. This check is intentionally local and evidence-based:
hero/reference assets must exist in `EXIT/visuals/` and in the corresponding
competition `media/` folder when the competition has a media surface.

## Required Hero Assets

| Competition | EXIT visual | Competition media | Status |
|---|---|---|---|
EOF

rows=(
  "PrizeHunter brand|$VIS/prizehunter-brand-hero.png|$VIS/prizehunter-brand-hero.png"
  # add your own: "Name|$VIS/your-hero.png|<reference image path>"
)

missing=0
for row in "${rows[@]}"; do
  IFS='|' read -r name exit_path media_path <<<"$row"
  status="PASS"
  [ -s "$exit_path" ] || status="MISSING_EXIT"
  [ -s "$media_path" ] || status="${status}_MISSING_MEDIA"
  if [ "$status" != "PASS" ]; then missing=$((missing+1)); fi
  exit_rel="${exit_path#$ROOT/}"
  media_rel="${media_path#$ROOT/}"
  printf '| %s | `%s` | `%s` | %s |\n' "$name" "$exit_rel" "$media_rel" "$status" >>"$OUT"
done

cat >>"$OUT" <<'EOF'

## Package Visual Inclusion

| Package | Visual entry | Status |
|---|---|---|
EOF

packages=(
  "ai-case_submission_20260613.zip|hero-reference.png"
  "ai-case_submission_20260612.zip|hero-reference.png"
  "ai-case-yaksa_submission_20260612.zip|hero-reference.png"
  "uipath_submission_20260612.zip|hero-reference.png"
  "moct_submission_20260612.zip|첨부_시제품및데이터/hero-reference.png"
  "moct_submission_20260612_mail.zip|첨부_시제품및데이터/hero-reference.png"
)

for row in "${packages[@]}"; do
  IFS='|' read -r zip_name entry <<<"$row"
  zip_path="$CONTROL/EXIT/packages/$zip_name"
  status="PASS"
  if [ ! -s "$zip_path" ]; then
    status="MISSING_ZIP"
  elif ! unzip -l "$zip_path" "$entry" >/dev/null 2>&1; then
    status="MISSING_VISUAL"
  fi
  if [ "$status" != "PASS" ]; then missing=$((missing+1)); fi
  printf '| `%s` | `%s` | %s |\n' "competitions/control_tower/EXIT/packages/$zip_name" "$entry" "$status" >>"$OUT"
done

cat >>"$OUT" <<'EOF'

Note: `moct_submission_20260612_enc.zip` is password-protected and is preserved
without adding an unencrypted visual file. The visualized MOCT package is the
normal/mail package pair above.

## Asset Dimensions

```text
EOF
for img in "$VIS"/*.png; do
  [ -e "$img" ] || continue
  file "$img" >>"$OUT"
done
cat >>"$OUT" <<'EOF'
```

## Codex Visual Gate

- PASS means each competition has a deck/submission-ready visual reference.
- Any future `ph run <key> --exec` or package finalization should refresh this
  file after changing visuals.
- External portal submission still depends on credentials/session availability,
  but visual QA should not be left to the founder.
EOF

echo "$OUT"
if [ "$missing" -gt 0 ]; then
  echo "visual_missing=$missing"
  exit 1
fi
echo "visual_missing=0"
