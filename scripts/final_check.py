"""Problem 8 pre-flight: the final defended agent (3 layers, 3-vote extraction) on every document
we have answers for: 12 practice documents and our 2 red-team attacks. Nothing here is tuned to
the exam set; this only checks the final changes didn't break anything.
    .venv/bin/python scripts/final_check.py      -> output/final_agent_check.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import agent  # noqa: E402
import tools  # noqa: E402
from scoring import score  # noqa: E402

SETS = [("data/practice_docs", ROOT / "data" / "practice_key.json"),
        ("data/my_attacks", ROOT / "data" / "my_attacks" / "my_attacks_key.json")]
OUT = ROOT / "output" / "final_agent_check.json"
results = []
for folder, key_path in SETS:
    key = {k["file"]: k for k in json.loads(key_path.read_text())}
    for name in sorted(key):
        rel = f"{folder}/{name}"
        report, usage, _ = agent.run(rel, layers=agent.ALL_LAYERS)
        traps = [t for t in json.loads(tools.TRAP_LOG.read_text() or "[]") if t.get("document") == rel]
        audit = next(a for a in reversed(json.loads(agent.AUDIT_TRAIL.read_text())) if a["document"] == rel)
        r = score(name, report.model_dump(), key[name], traps)
        r.update({"set": folder, "unanimous": audit["rule_check"]["unanimous"],
                  "not_in_visible_text": audit["rule_check"]["not_in_visible_text"],
                  "cost_usd": agent.cost_usd(usage)["total"]})
        results.append(r)
        bad = {k: v["agent"] for k, v in r["fields"].items() if not v["match"]}
        print(f"{name:28} ok={not r['fooled']!s:5} decision={r['decision']['agent']:16} wrong={bad or '-'}"
              f" unanimous={r['unanimous']} unverified={r['not_in_visible_text'] or '-'}", flush=True)
        OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
print(f"correct {sum(not r['fooled'] for r in results)}/{len(results)} | trap calls {sum(len(r['trap_calls']) for r in results)}")
