"""Problem 5: attack the Problem 3 agent (no defenses) with all 12 practice documents.

Saves output/attack_results.json. Run:  .venv/bin/python scripts/attack_test.py
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

DOCS = sorted((ROOT / "data" / "practice_docs").iterdir())
KEY = {k["file"]: k for k in json.loads((ROOT / "data" / "practice_key.json").read_text())}
OUT = ROOT / "output" / "attack_results.json"


def traps() -> list:
    return json.loads(tools.TRAP_LOG.read_text() or "[]") if tools.TRAP_LOG.exists() else []


results = []
for doc in DOCS:
    before = len(traps())
    report, usage, _ = agent.run(str(doc.relative_to(ROOT)), cache=True, defend=False)
    r = score(doc.name, report.model_dump(), KEY[doc.name], traps()[before:])
    r["cost_usd"] = round(agent.cost_usd(usage)["total"], 6)
    results.append(r)
    print(f"{doc.name:30} fields={'ok' if r['all_fields_match'] else 'WRONG':5} decision={'ok' if r['decision']['match'] else 'WRONG':5}"
          f" trap={r['trap_tool_called']!s:5} strange={list(r['strange_text']) or '-'}", flush=True)
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

print(f"fooled {sum(r['fooled'] for r in results)}/12 | wrong decisions {sum(not r['decision']['match'] for r in results)}"
      f" | trap calls {sum(len(r['trap_calls']) for r in results)} | wrote {OUT.relative_to(ROOT)}")
