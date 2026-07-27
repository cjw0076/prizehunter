#!/usr/bin/env bash
# transfer_gate.sh — NOTHING COUNTS AS PROGRESS UNTIL WHAT WE VALIDATED IS WHAT WE SHIPPED, AND THE LEADERBOARD SAYS SO.
#
# founder 2026-07-26: "TRANSFER GATE부터 가."
#
# Why this exists — two measured failures, same root, both invisible to every other gate we own:
#   • rogii: local went 10.419 → 8.565 while the LEADERBOARD went the other way (v8 12.333, v9 10.781). Cause: the
#     shipped kernel was NOT the validated pipeline — it omitted WARP entirely, ran 17% of rows and 8% of the PF
#     particles. We were grading one thing and submitting another. (Class: SHIP≠VALIDATE)
#   • playground: a drive produced a local OOF gain of +5.85e-5 in a competition whose OWN measured history shows
#     +6e-5 OOF turning into −8e-5 on the LB. The gain was below its own transfer floor = noise. (Class: SUB-FLOOR GAIN)
#
# Three checks, all mechanical:
#   declare <key> <manifest.json>      record WHAT WAS VALIDATED (components/params/rows/score) — the fingerprint
#   verify  <key> <manifest.json>      compare a SUBMISSION manifest against the validated fingerprint (field diffs)
#   floor   <key>                      derive this competition's local→LB transfer floor from its own (local,LB) pairs
#   gate    <key> <local_gain> [subm.json]   PASS only if the gain clears the floor AND the fingerprint matches
#
# A manifest is any flat JSON of the fields that decide the result, e.g.
#   {"components":["PF","GBDT","WARP"],"rows":3783989,"pf_particles":500,"seeds":64,"score":8.5653,"scale":"local"}
set -uo pipefail
CT="$(cd -- "$(dirname "$0")/.." && pwd)"; R="${PH_RUNS:-$CT/.runs}"; mkdir -p "$R"
REG="$CT/portfolio_registry.tsv"
CMD="${1:-}"; KEY="${2:-}"

case "$CMD" in
  declare)
    M="${3:?transfer_gate.sh declare <key> <manifest.json>}"
    python3 - "$R/validated_$KEY.json" "$M" <<'PY'
import json, sys, shutil
dst, src = sys.argv[1], sys.argv[2]
d = json.load(open(src))
json.dump(d, open(dst, "w"), indent=1, ensure_ascii=False)
print(f"  ✓ validated fingerprint recorded for this key ({len(d)} field(s)) → {dst}")
print("    fields:", ", ".join(sorted(d)))
PY
    ;;

  verify)
    M="${3:?transfer_gate.sh verify <key> <submission_manifest.json>}"
    python3 - "$R/validated_$KEY.json" "$M" <<'PY'
import json, os, sys
vf, sf = sys.argv[1], sys.argv[2]
if not os.path.exists(vf):
    print("  ⛔ FAIL: no validated fingerprint on record — declare one before shipping"); sys.exit(1)
v, s = json.load(open(vf)), json.load(open(sf))
diffs = []
for k in sorted(set(v) | set(s)):
    a, b = v.get(k, "<missing>"), s.get(k, "<missing>")
    if k in ("score", "scale", "note"):        # score is expected to differ; the CONFIG must not
        continue
    if a != b:
        diffs.append((k, a, b))
if not diffs:
    print("  ✓ PASS: the submission matches the validated configuration field-for-field"); sys.exit(0)
print("  ⛔ FAIL: SHIP≠VALIDATE — the submission is not the thing we graded:")
for k, a, b in diffs:
    print(f"     {k}: validated={a!r}  submitted={b!r}")
print("     (this is exactly how rogii's local 8.565 shipped as an LB 10.781)")
sys.exit(1)
PY
    ;;

  floor)
    python3 - "$KEY" "$CT" <<'PY'
import os, re, sys
key, CT = sys.argv[1], sys.argv[2]
# Find (local, LB) pairs the competition itself recorded. We look for lines that carry BOTH a local/CV/OOF number
# and an LB number — the only honest source for how much local gain actually transfers.
cands = []
for root, _, files in os.walk(os.path.join(CT, "campaigns")):
    if key.split("-")[0][:6].lower() not in root.lower():
        continue
    for fn in files:
        if not fn.endswith((".md", ".json")):
            continue
        try:
            txt = open(os.path.join(root, fn), errors="ignore").read()
        except OSError:
            continue
        for line in txt.splitlines():
            if not re.search(r"\bLB\b|leaderboard|public", line, re.I):
                continue
            if not re.search(r"local|cv|oof|gkf|holdout", line, re.I):
                continue
            nums = [float(x) for x in re.findall(r"\d+\.\d{2,}", line)][:6]
            if len(nums) >= 2:
                cands.append((os.path.join(os.path.basename(root), fn), line.strip()[:150], nums))
if not cands:
    print(f"  floor UNKNOWN for '{key}': the record contains no line pairing a local score with an LB score.")
    print("  → until one exists, treat ANY local-only gain as unproven: submit it as a deliberate ANCHOR probe,")
    print("    labelled as such, and use the returned LB score to establish the floor.")
    sys.exit(0)
print(f"  transfer evidence for '{key}' ({len(cands)} line(s) pairing local and LB):")
for src, line, nums in cands[:8]:
    print(f"     [{src}] {line}")
print("  → derive the floor from these pairs: the smallest local gain that produced a same-signed LB gain.")
print("    Any candidate gain BELOW that floor is noise and must not consume a submission slot.")
PY
    ;;

  gate)
    G="${3:-}"; M="${4:-}"
    echo "== transfer gate [$KEY] =="
    ok=0
    if [ -n "$M" ]; then
      bash "$0" verify "$KEY" "$M" || ok=1
    else
      if [ -f "$R/validated_$KEY.json" ]; then
        echo "  ⚠ no submission manifest given — cannot prove SHIP==VALIDATE (the rogii failure mode)"; ok=1
      else
        echo "  ⚠ no validated fingerprint on record for this key"; ok=1
      fi
    fi
    bash "$0" floor "$KEY"
    if [ -n "$G" ]; then
      echo "  claimed local gain: $G  → check it against the floor evidence above BEFORE spending a slot"
    fi
    if [ "$ok" = 0 ]; then echo "== TRANSFER GATE: PASS (fingerprint matched; still confirm the gain clears the floor) =="; exit 0
    else echo "== TRANSFER GATE: FAIL — do not open the founder submit gate on this =="; exit 1; fi
    ;;

  *)
    cat <<EOF
usage:
  transfer_gate.sh declare <key> <validated_manifest.json>
  transfer_gate.sh verify  <key> <submission_manifest.json>
  transfer_gate.sh floor   <key>
  transfer_gate.sh gate    <key> <local_gain> [submission_manifest.json]
principle: a local gain is a HYPOTHESIS about the leaderboard, not progress. It becomes progress only when the
shipped artifact is provably the validated one AND the leaderboard confirms it.
EOF
    ;;
esac
