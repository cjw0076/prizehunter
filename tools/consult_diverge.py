#!/usr/bin/env python3
"""Read a panel round and surface DISAGREEMENT, because that is the part worth verifying.

A heterogeneous panel is worth ~2 effective independent votes (measured), so consensus is weak evidence
and unanimity can be shared hallucination. What no single substrate can fake is a number another substrate
contradicts — so this ranks the panel by divergence and hands back a verification queue, not a summary.
"""
import re
import sys


def main(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    parts = re.split(r"\n### ", t)
    subs = []
    for p in parts[1:]:
        name = p.split("\n", 1)[0].strip()
        body = p.split("\n", 1)[1] if "\n" in p else ""
        nums = set()
        for m in re.finditer(r"\d\.?\d*\s*[eE][-+]?\d+", body):
            try:
                nums.add(float(m.group(0).replace(" ", "")))
            except ValueError:
                pass
        subs.append((name, body, nums))
    print("== PANEL: %d substrate(s) answered ==" % len(subs))
    for n, b, nums in subs:
        print("  %-28s %6d chars · %2d numeric claims" % (n[:28], len(b), len(nums)))
    if len(subs) < 2:
        print("\n  only one substrate answered — this is not a panel, treat it as a single opinion")
        return 0
    inter = set.intersection(*[s[2] for s in subs if s[2]]) if all(s[2] for s in subs) else set()
    print("\n-- numbers EVERY substrate produced (weak signal ~2 effective votes — still verify):")
    print("   %s" % (sorted(inter)[:10] or "none"))
    print("\n-- THE PAYLOAD: numbers only one substrate produced (verify these first)")
    for n, b, nums in subs:
        others = set().union(*[s[2] for s in subs if s[0] != n])
        uniq = sorted(nums - others)
        if uniq:
            print("   %-28s %s" % (n[:28], ["%.3g" % u for u in uniq[:8]]))
    # contradiction hunt: same order of magnitude claimed differently is not a contradiction; a different
    # ORDER for the same quantity is. Report exponent spread as the cheap proxy.
    import math
    print("\n-- exponent spread per substrate (a 2+ decade spread on the same question = someone is wrong):")
    for n, b, nums in subs:
        ex = [int(math.floor(math.log10(abs(x)))) for x in nums if x]
        if ex:
            print("   %-28s 10^%d … 10^%d" % (n[:28], min(ex), max(ex)))
    print("\n-- next: reproduce the unique claims on our harness, then: ph consult adopt <key>")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
