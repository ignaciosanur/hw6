"""Problem 7: run our two red-team documents against the agent with no defenses and with all three.

Each document x setup runs RUNS times (the model is not deterministic). Saves output/red_team_results.json.
    .venv/bin/python scripts/red_team_test.py                      # no_defense + defended
    .venv/bin/python scripts/red_team_test.py code_design_only     # which layer stopped it? (merged in)
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import agent  # noqa: E402
import tools  # noqa: E402
from scoring import score  # noqa: E402

RUNS = 3
KEY = {k["file"]: k for k in json.loads((ROOT / "data" / "my_attacks" / "my_attacks_key.json").read_text())}
OUT = ROOT / "output" / "red_team_results.json"
SETUPS = {"no_defense": agent.NO_LAYERS, "defended": agent.ALL_LAYERS,
          "code_design_only": frozenset({"code", "design"}), "prompt_only": frozenset({"prompt"})}
CHOSEN = sys.argv[1:] or ["no_defense", "defended"]


def job(doc: str, setup: str) -> list[dict]:
    rel = f"data/my_attacks/{doc}"
    out = []
    for i in range(1, RUNS + 1):
        report, usage, _ = agent.run(rel, cache=True, layers=SETUPS[setup])
        audit = next(a for a in reversed(json.loads(agent.AUDIT_TRAIL.read_text()))
                     if a["document"] == rel and a["defense_layers"] == sorted(SETUPS[setup]))
        traps = [t for t in json.loads(tools.TRAP_LOG.read_text() or "[]") if t.get("document") == rel]
        r = score(doc, report.model_dump(), KEY[doc], traps)
        r.update({"setup": setup, "run": i, "hidden_content_removed": audit["hidden_content_removed"],
                  "blocked_tool_calls": audit["blocked_tool_calls"], "cost_usd": agent.cost_usd(usage)["total"],
                  "tokens": {"input": usage.input_tokens, "output": usage.output_tokens, "requests": usage.requests}})
        out.append(r)
        bad = {k: v["agent"] for k, v in r["fields"].items() if not v["match"]}
        print(f"{setup:10} {doc:24} run {i}: decision={r['decision']['agent']:16} fooled={r['fooled']!s:5} wrong={bad or '-'}", flush=True)
    return out


# One thread per setup: each setup has its own agent (and HTTP client), which can't be shared across threads.
with ThreadPoolExecutor(max_workers=len(CHOSEN)) as pool:
    new = [r for batch in pool.map(lambda s: [x for d in KEY for x in job(d, s)], CHOSEN) for r in batch]
old = [r for r in json.loads(OUT.read_text()) if r["setup"] not in CHOSEN] if OUT.exists() else []
results = old + new
OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
for d in KEY:
    for s in [x for x in SETUPS if any(r["setup"] == x for r in results)]:
        rs = [r for r in results if r["document"] == d and r["setup"] == s]
        print(f"{d:24} {s:10} fooled {sum(r['fooled'] for r in rs)}/{len(rs)}")
