#!/usr/bin/env python3
"""make_presentation_kit.py — auto-generate the presentation deliverables.

Produces, into campaigns/<key>/deliverables/:
  SLIDES.md           — winning-pitch deck (markdown; render to pptx/pdf when a
                        renderer exists — marp/pandoc absent here, so content-only)
  TALK_SCRIPT.md      — per-slide speaker script + Q&A prep (for live presentation)
  VIDEO_STORYBOARD.md — shot list w/ timestamps + narration + on-screen action
                        (recording itself is human-gated; this is the full plan)

These are the agent-producible parts of video/presentation deliverables. The
human only records/uploads. Pull real numbers from PLAN + results to avoid fluff.

Usage:
  make_presentation_kit.py --key <your-key> [--results "best 0.91, rank 3->1 lever X"]
"""
import json, os, argparse

DECK = [
    ("Title", "{name}", "one line: what it is + the headline result"),
    ("Problem", "the competition's real challenge", "why it's hard / what naive approaches miss"),
    ("Approach", "our method", "the rank-1 lever + honest-CV discipline (no leaderboard overfit)"),
    ("Demo", "it works", "one-command reproducible run; show the live output"),
    ("Results", "the numbers", "{results}; vs baseline / vs rank-1"),
    ("Why it generalizes", "honesty", "leak-checked, signal-ceiling-aware — trustworthy, not overfit"),
    ("Impact / Close", "the ask", "reusability, what's next, thank you"),
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--results", default="(fill from leaderboard + CV)")
    here = os.path.dirname(__file__)
    ap.add_argument("--campaigns", default=os.path.join(here, "..", "campaigns"))
    a = ap.parse_args()

    pj = os.path.join(a.campaigns, a.key, "PLAN.json")
    name = a.key
    if os.path.exists(pj):
        name = json.load(open(pj)).get("name", a.key)
    out = os.path.join(a.campaigns, a.key, "deliverables"); os.makedirs(out, exist_ok=True)

    def fill(s): return s.format(name=name, results=a.results)

    with open(os.path.join(out, "SLIDES.md"), "w") as o:
        o.write(f"<!-- deck: {name}. render with marp/pandoc when available -->\n")
        for i, (t, head, body) in enumerate(DECK, 1):
            o.write(f"\n---\n\n# {i}. {t}\n\n## {fill(head)}\n\n- {fill(body)}\n")

    with open(os.path.join(out, "TALK_SCRIPT.md"), "w") as o:
        o.write(f"# Speaker script — {name}\n\nPacing: ~40s/slide, ~5min total. Speak to the result, not the slide.\n")
        for i, (t, head, body) in enumerate(DECK, 1):
            o.write(f"\n## Slide {i}: {t} (~40s)\n> {fill(head)} — {fill(body)}\n\n"
                    f"_Say:_ \"...\"  (fill: 2-3 sentences hitting {t.lower()}; land the number on Results.)\n")
        o.write("\n## Q&A prep\n- Q: is it overfit? A: leak-checked + honest future-block CV; show the gap.\n"
                "- Q: does it generalize? A: signal-ceiling analysis; ceiling is data-bound, not approach-bound.\n"
                "- Q: reproducible? A: one-command demo, public MIT repo.\n")

    with open(os.path.join(out, "VIDEO_STORYBOARD.md"), "w") as o:
        o.write(f"# Demo video storyboard — {name}  (<5min)\n\n"
                "Recording is human (screen+voice). This is the full shot plan + narration.\n\n"
                "| t | shot | on-screen | narration |\n|---|---|---|---|\n")
        shots = [
            ("0:00", "title card", "repo + competition name", "what this is in one sentence"),
            ("0:20", "problem", "data/task screenshot", "the challenge + why it's hard"),
            ("0:50", "approach", "architecture / method diagram", "the rank-1 lever"),
            ("1:40", "live demo", "terminal: one-command run", "watch it run end-to-end"),
            ("3:00", "results", "leaderboard + CV table", fill("{results}")),
            ("4:00", "honesty+impact", "leak/ceiling check", "why it's trustworthy + reusable"),
            ("4:40", "close", "repo URL + thanks", "call to action"),
        ]
        for t, shot, scr, narr in shots:
            o.write(f"| {t} | {shot} | {scr} | {narr} |\n")

    print(out)
    print("generated: SLIDES.md, TALK_SCRIPT.md, VIDEO_STORYBOARD.md")

if __name__ == "__main__":
    main()
