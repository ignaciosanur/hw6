"""Problem 4: run the agent on all 12 practice documents with and without prompt caching.

Saves every model call (not just every run) to output/cache_test.json.
    .venv/bin/python scripts/cache_test.py                  # both setups
    .venv/bin/python scripts/cache_test.py without_cache    # re-run one setup, keep the other's calls
Then build the report with scripts/cache_report.py.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agent  # noqa: E402
import tools  # noqa: E402

DOCS = sorted((ROOT / "data" / "practice_docs").iterdir())
KEY = {k["file"]: k for k in json.loads((ROOT / "data" / "practice_key.json").read_text())}
OUT = ROOT / "output" / "cache_test.json"
FIELDS = ("vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision")

SETUPS = {"without_cache": False, "with_cache": True}
chosen = sys.argv[1:] or list(SETUPS)
calls = [c for c in json.loads(OUT.read_text())] if OUT.exists() else []
calls = [c for c in calls if c["setup"] not in chosen]
# Without cache first, so nothing this script does can warm the cache for it.
for setup in chosen:
    cache = SETUPS[setup]
    for doc in DOCS:
        rel = str(doc.relative_to(ROOT))
        report, _, per_request = agent.run(rel, cache=cache, defend=False)  # the agent as built in Problem 3
        key = KEY[doc.name]
        correct = {f: getattr(report, f) == key[f] for f in FIELDS}
        for i, req in enumerate(per_request, 1):
            calls.append({"setup": setup, "document": doc.name, "request": i, "time": tools.now(),
                          "model": agent.MODEL_NAME, **req,
                          "decision": report.decision, "decision_correct": correct["decision"],
                          "fields_correct": sum(correct.values())})
        u = per_request
        print(f"{setup:14} {doc.name:30} requests={len(u)} in={sum(r['input_tokens'] for r in u):>6,}"
              f" cached={sum(r['cached_tokens'] for r in u):>6,} write={sum(r['cache_write_tokens'] for r in u):>6,}"
              f" ${sum(r['cost_usd']['total'] for r in u):.6f}  {report.decision} {'✓' if correct['decision'] else '✗'}", flush=True)
        OUT.write_text(json.dumps(calls, indent=2) + "\n")  # save as we go

print(f"wrote {len(calls)} model calls to {OUT.relative_to(ROOT)}")
