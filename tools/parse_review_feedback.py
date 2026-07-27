#!/usr/bin/env python3
"""
parse_review_feedback.py — read FEEDBACK_REQUEST.md after founder fills it in,
extract answers, log to founder_requests.md as a structured revision task.
Usage: python3 parse_review_feedback.py <campaign_key>
"""
import sys, os, re, glob, pathlib, datetime

PH_HOME = pathlib.Path(__file__).parent.parent
KEY = sys.argv[1] if len(sys.argv) > 1 else None
if not KEY:
    print("Usage: parse_review_feedback.py <campaign_key>"); sys.exit(1)

# Find FEEDBACK_REQUEST.md
camp_dirs = list(PH_HOME.glob(f"campaigns/*{KEY}*"))
if not camp_dirs:
    print(f"ERROR: no campaign dir for key={KEY}"); sys.exit(1)
form_path = camp_dirs[0] / "FEEDBACK_REQUEST.md"
if not form_path.exists():
    print(f"ERROR: FEEDBACK_REQUEST.md not found at {form_path}"); sys.exit(1)

text = form_path.read_text()

def extract_checked(q_block):
    """Return checked option letter, or None."""
    for line in q_block.split('\n'):
        m = re.match(r'\s*-\s*\[x\]\s*([A-Z])\s*[—–-]', line, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None

def extract_freetext(label, text):
    """Extract content after >  following a label."""
    pattern = rf'###\s*{re.escape(label)}.*?\n>(.*?)(?=###|\Z)'
    m = re.search(pattern, text, re.DOTALL)
    if m:
        val = m.group(1).strip()
        return val if val else None
    return None

q1 = extract_checked(re.search(r'### Q1.*?(?=### Q2)', text, re.DOTALL).group() if re.search(r'### Q1.*?(?=### Q2)', text, re.DOTALL) else '')
q2 = extract_checked(re.search(r'### Q2.*?(?=### Q3)', text, re.DOTALL).group() if re.search(r'### Q2.*?(?=### Q3)', text, re.DOTALL) else '')
q3 = extract_checked(re.search(r'### Q3.*?(?=### Q4)', text, re.DOTALL).group() if re.search(r'### Q3.*?(?=### Q4)', text, re.DOTALL) else '')
improve = extract_freetext('Q4', text)
good = extract_freetext('Q5', text)
score_m = re.search(r'### Q6.*?\n>(.*?)(?=###|\Z)', text, re.DOTALL)
score = score_m.group(1).strip() if score_m else None
directive = extract_freetext('Q7', text)

# Determine status
grade = q1 or '?'
needs_revision = grade in ('B', 'C', 'D')
status = 'pending' if needs_revision else 'approved'

summary_lines = [f"Q1={q1} Q2={q2} Q3={q3} 만족도={score}"]
if improve:
    summary_lines.append(f"개선: {improve[:200]}")
if good:
    summary_lines.append(f"유지: {good[:200]}")
if directive:
    summary_lines.append(f"지시: {directive[:200]}")

ts = datetime.datetime.utcnow().strftime('%Y-%m-%d')
req_file = PH_HOME / 'founder_requests.md'

block = f"""
## [{status}] {KEY} — {ts} (review feedback)

**평가**: {' | '.join(summary_lines)}

**Worker 작업**:
"""
if needs_revision:
    if improve:
        block += f"- [ ] 개선: {improve[:300]}\n"
    if directive:
        block += f"- [ ] 지시: {directive[:300]}\n"
    if grade == 'D':
        block += "- [ ] 전면 재작성\n"
else:
    block += "- [x] APPROVED — 제출 준비 완료\n"

with open(req_file, 'a') as f:
    f.write(block)

print(f"Feedback parsed: Q1={q1} Q2={q2} Q3={q3} score={score} status={status}")
print(f"Logged to: {req_file}")
if needs_revision:
    print(f"→ Worker revision required. Run: ph requests")
else:
    print(f"→ APPROVED. Ready to package and notify founder for external submission.")
