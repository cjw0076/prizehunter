import json,sys
try: d=json.load(sys.stdin)
except Exception: print("(no context pack)"); sys.exit()
print(f"# trace_id={d.get('trace_id')}")
seen=0
for sec in ("decisions","facts","memories","nodes"):
    for it in (d.get(sec) or [])[:8]:
        c=(it.get("content") or "").strip().replace("\n"," ")
        if c:
            print(f"- [{it.get('type',sec)}] {c[:200]}"); seen+=1
if not seen: print("- (no accumulated expertise yet — deposit campaigns to grow it)")
