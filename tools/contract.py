#!/usr/bin/env python3
"""contract.py — HARNESS CONTRACT ENFORCER. Fail loudly on output you cannot read.

The failure this exists to prevent (measured, 2026-07-27): the autonomous loop's eval step looked for JSON keys
named `score`/`mse` while the harness emits `adjusted_final_layer_score`. Every evaluation logged the string
"unparsed", the loop could not rank anything, and it would have generated candidates forever while looking
busy. It ran one round before I caught it — and I only caught it because I stepped out and watched. A human in
the loop reads the JSON with their eyes and never notices the loop cannot.

So: every machine-to-machine handoff declares a contract, and a violation is an ERROR with exit code 65
(EX_DATAERR), not a silently-recorded empty string. agy's framing, adopted: "the execution plane lacks strict
schema guardrails" — the guardrail is cheaper than the supervision it replaces.

    contract.py check <schema> <file>       validate; exit 0 ok, 65 on violation (prints what was wrong)
    contract.py extract <schema> <file>     validate then print the extracted fields as TSV (for shell use)
    contract.py selftest                    prove the enforcer rejects a wrong shape in <100ms

Schemas are named, tiny, and live in this file — a schema in a separate file that nobody updates is how the
contract silently drifts from the harness.
"""
import json
import os
import re
import sys
import time

# name -> {field: [acceptable json keys, in priority order]}
# The ordering matters: for whestbench, `adjusted_final_layer_score` is the number the platform ranks on, so a
# reader that grabs `final_layer_mse` first would rank variants on the wrong quantity and never know.
SCHEMAS = {
    "whest_eval": {
        "score": ["adjusted_final_layer_score", "adjusted_score"],
        "final_layer_mse": ["final_layer_mse"],
        "all_layers_mse": ["all_layers_mse"],
        "flop_budget": ["flop_budget"],
        "flops_used": ["flops_used"],
    },
    "whest_submit": {
        "submission_id": ["submission_id", "id"],
        "score": ["score", "adjusted_score"],
    },
    "verdict": {
        "verdict": ["verdict"],
        "reason": ["reason"],
    },
}
REQUIRED = {"whest_eval": ["score"], "whest_submit": ["submission_id"], "verdict": ["verdict"]}
EX_DATAERR = 65


def dig(obj, keys):
    """Depth-first search for the first key in `keys` whose value is a scalar."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in keys and isinstance(v, (int, float, str)) and not isinstance(v, bool):
                return v
            r = dig(v, keys)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = dig(v, keys)
            if r is not None:
                return r
    return None


def load_json_blob(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None, "no JSON object found in %d bytes of output" % len(raw)
    try:
        return json.loads(m.group(0)), None
    except json.JSONDecodeError as e:
        return None, "JSON present but unparseable: %s" % str(e)[:120]


def check(schema_name, path, quiet=False):
    if schema_name not in SCHEMAS:
        print("contract: unknown schema %r (known: %s)" % (schema_name, ", ".join(sorted(SCHEMAS))))
        return EX_DATAERR, {}
    if not os.path.exists(path):
        print("contract VIOLATION [%s]: file does not exist: %s" % (schema_name, path))
        return EX_DATAERR, {}
    obj, err = load_json_blob(path)
    if obj is None:
        print("contract VIOLATION [%s] %s: %s" % (schema_name, os.path.basename(path), err))
        return EX_DATAERR, {}
    out = {}
    for field, keys in SCHEMAS[schema_name].items():
        v = dig(obj, {k.lower() for k in keys})
        if v is not None:
            out[field] = v
    missing = [f for f in REQUIRED[schema_name] if f not in out]
    if missing:
        print("contract VIOLATION [%s] %s: required field(s) %s not found. Accepted keys were %s. "
              "Top-level keys present: %s"
              % (schema_name, os.path.basename(path), missing,
                 {f: SCHEMAS[schema_name][f] for f in missing},
                 list(obj.keys())[:10]))
        return EX_DATAERR, out
    if not quiet:
        print("contract OK [%s] %s: %s" % (schema_name, os.path.basename(path),
                                           " ".join("%s=%s" % (k, v) for k, v in out.items())))
    return 0, out


def selftest():
    """A guardrail that has never rejected anything is not known to work."""
    import tempfile
    t0 = time.time()
    fails = 0
    with tempfile.TemporaryDirectory() as d:
        bad = os.path.join(d, "bad.json")
        open(bad, "w").write('{"result": 0.5}')                      # the shape agy proposed as the test
        rc, _ = check("whest_eval", bad, quiet=True)
        print("  %s wrong-shape input rejected (rc=%d)" % ("✓" if rc == EX_DATAERR else "✗", rc))
        fails += rc != EX_DATAERR
        good = os.path.join(d, "good.json")
        open(good, "w").write('{"results": {"adjusted_final_layer_score": 2.1e-6, "final_layer_mse": 5.7e-6}}')
        rc, out = check("whest_eval", good, quiet=True)
        ok = rc == 0 and abs(float(out.get("score", 0)) - 2.1e-6) < 1e-12
        print("  %s correct input accepted and score extracted (%s)" % ("✓" if ok else "✗", out.get("score")))
        fails += not ok
        empty = os.path.join(d, "empty.log")
        open(empty, "w").write("Traceback (most recent call last):\n  RuntimeError: numba missing\n")
        rc, _ = check("whest_eval", empty, quiet=True)
        print("  %s traceback-only output rejected (rc=%d)" % ("✓" if rc == EX_DATAERR else "✗", rc))
        fails += rc != EX_DATAERR
        rc, _ = check("whest_eval", os.path.join(d, "nope.json"), quiet=True)
        print("  %s missing file rejected (rc=%d)" % ("✓" if rc == EX_DATAERR else "✗", rc))
        fails += rc != EX_DATAERR
    ms = 1000 * (time.time() - t0)
    print("  selftest %s in %.0fms (agy's criterion: reject a wrong shape in <100ms)"
          % ("PASSED" if not fails else "FAILED", ms))
    return 0 if not fails else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().split("\n\n")[-2])
        return 2
    cmd = sys.argv[1]
    if cmd == "selftest":
        return selftest()
    if cmd in ("check", "extract") and len(sys.argv) >= 4:
        rc, out = check(sys.argv[2], sys.argv[3], quiet=(cmd == "extract"))
        if cmd == "extract" and rc == 0:
            print("\t".join(str(out.get(f, "")) for f in SCHEMAS[sys.argv[2]]))
        return rc
    print("usage: contract.py check|extract <schema> <file> | selftest")
    return 2


if __name__ == "__main__":
    sys.exit(main())
