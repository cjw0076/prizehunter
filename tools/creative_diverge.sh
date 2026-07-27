#!/usr/bin/env bash
# creative_diverge.sh — anti-AI-default creative challenge before locking a storyline.
# Forces 5+ wildly different framings. Run BEFORE building any submission content.
# Usage: bash creative_diverge.sh <topic> [competition_key]
set -u
TOPIC="${1:?need topic}"
KEY="${2:-unknown}"

cat << EOF
╔═══════════════════════════════════════════════════════════════╗
║  CREATIVE DIVERGENCE — anti-AI-default protocol              ║
║  Topic: $TOPIC
╚═══════════════════════════════════════════════════════════════╝

RULE: Do NOT use the first idea. The first idea is always the average.
      Generate all 5 framings, then pick the most surprising one.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Challenge 1] — REVERSED NARRATOR
  Standard: "researcher analyzes data to find problem"
  → Who is the UNEXPECTED narrator? The data itself? An affected child?
    An AI model that fails to understand the problem? The empty concert hall?
  Your alternative:

[Challenge 2] — FIND THE SPECIFIC DETAIL
  Standard: "a region has low cultural access"
  → What is the ONE specific, unforgettable detail that makes this real?
    The name of a closed theater. The last bus at 9pm. The year the piano was sold.
  Your specific detail:

[Challenge 3] — STRUCTURAL INVERSION
  Standard: Problem → Analysis → Solution
  → What if you start at the END (what 2030 looks like if we solve/don't solve this)?
    Or a letter from the future? Or data that tells a story backwards?
  Your structure:

[Challenge 4] — UNEXPECTED COMPARISON
  Standard: compare regions within Korea
  → What is the WILDEST valid comparison? Seoul's 8 concerts/year vs.
    Vienna's 200? A data center that uses more electricity than all the concerts it streams?
    The cost of one Gangnam apartment = funding 200 regional concert halls?
  Your comparison:

[Challenge 5] — DATA AS ART / ANTI-CHART
  Standard: bar charts, scatter plots, K-Means cluster scatter
  → What if the visualization IS the argument? A map where the cultural desert
    is literally blank white space. A receipt for "0 concerts" vs. "8 concerts."
    Sound wave visualization of silence vs. music. An empty seat counter.
  Your visual idea:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANTI-SLOP CHECK:
  ☐ Does the title contain "AI기반", "데이터 분석", "효율화", "최적화"? → RENAME it
  ☐ Does the intro start with "한국은..." or "최근..." or "현대사회에서..."? → CUT IT
  ☐ Is the methodology just GBR + K-Means? → What's the surprising 3rd thing?
  ☐ Does the conclusion say "향후 연구 방향"? → DELETE it, end with an image
  ☐ Are the charts 2×2 matplotlib subplots? → Consider: what chart type has never
     been used in this competition before?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STORYLINE RULE: Connection is everything. There are no limits.
  A cultural desert analysis can be connected to:
  → A cartographer who maps what isn't there
  → The physics of sound in empty rooms
  → The economy of longing (what do people do when culture is absent?)
  → A child's question that an algorithm can't answer
  → The inverse: a city that has TOO much culture and what it displaces

The best angle is the one that makes the reader feel something
AND presents the data honestly. Never sacrifice one for the other.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Log this session → ph learn --summary "$KEY: [winning angle chosen]"
EOF
