"""Problem 6: re-run all 12 practice documents with the defenses on.

Setups (run in parallel, one thread each):
  all     code + design + prompt   -> output/defense_results.json (the "after")
  code    code layer only          \\
  design  design layer only         } -> output/defense_layers.json, to see what each layer catches
  prompt  prompt layer only        /
The "before" is Problem 5's output/attack_results.json (no layers).
    .venv/bin/python scripts/defense_test.py            # all four setups
    .venv/bin/python scripts/defense_test.py all        # just the full defense
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

DOCS = sorted((ROOT / "data" / "practice_docs").iterdir())
KEY = {k["file"]: k for k in json.loads((ROOT / "data" / "practice_key.json").read_text())}
SETUPS = {"all": {"code", "design", "prompt"}, "code": {"code"}, "design": {"design"}, "prompt": {"prompt"}}
OUT_ALL = ROOT / "output" / "defense_results.json"
OUT_LAYERS = ROOT / "output" / "defense_layers.json"


def run_setup(name: str) -> list[dict]:
    out = []
    for doc in DOCS:
        rel = str(doc.relative_to(ROOT))
        trap_before = {json.dumps(t) for t in json.loads(tools.TRAP_LOG.read_text() or "[]")}
        blocked_before = len(json.loads(tools.BLOCKED_LOG.read_text())) if tools.BLOCKED_LOG.exists() else 0
        report, usage, per_request = agent.run(rel, cache=True, layers=frozenset(SETUPS[name]))
        new_traps = [t for t in json.loads(tools.TRAP_LOG.read_text() or "[]")
                     if json.dumps(t) not in trap_before and t.get("document") == rel]
        blocked = [b for b in (json.loads(tools.BLOCKED_LOG.read_text()) if tools.BLOCKED_LOG.exists() else [])[blocked_before:]
                   if b["document"] == rel]
        audit = next(a for a in reversed(json.loads(agent.AUDIT_TRAIL.read_text())) if a["document"] == rel
                     and a.get("defense_layers") == sorted(SETUPS[name]))
        r = score(doc.name, report.model_dump(), KEY[doc.name], new_traps)
        cost = agent.cost_usd(usage)
        r.update({
            "setup": name, "layers": sorted(SETUPS[name]),
            "blocked_tool_calls": blocked,                       # held for sign-off, never ran
            "hidden_content_removed": audit["hidden_content_removed"],
            "tokens": {"requests": usage.requests, "input": usage.input_tokens, "cached": usage.cache_read_tokens,
                       "cache_write": usage.cache_write_tokens, "output": usage.output_tokens,
                       "reasoning": usage.details.get("reasoning_tokens", 0)},
            "cost_usd": cost,
            # Same tokens at the plain input/output price, so setups compare without cache luck.
            "list_price_usd": round(usage.input_tokens * agent.PRICES["input_per_1m"] / 1e6
                                    + usage.output_tokens * agent.PRICES["output_per_1m"] / 1e6, 8),
        })
        out.append(r)
        print(f"{name:7} {doc.name:30} fooled={r['fooled']!s:5} decision={'ok' if r['decision']['match'] else 'WRONG':5}"
              f" fields={'ok' if r['all_fields_match'] else 'WRONG':5} blocked={len(blocked)} req={usage.requests}"
              f" in={usage.input_tokens:,} out={usage.output_tokens} ${cost['total']:.6f}", flush=True)
    return out


chosen = sys.argv[1:] or list(SETUPS)
with ThreadPoolExecutor(max_workers=len(chosen)) as pool:
    results = dict(zip(chosen, pool.map(run_setup, chosen)))

if "all" in results:
    OUT_ALL.write_text(json.dumps(results["all"], indent=2, ensure_ascii=False) + "\n")
layers = {k: v for k, v in results.items() if k != "all"}
if layers:
    old = json.loads(OUT_LAYERS.read_text()) if OUT_LAYERS.exists() else {}
    OUT_LAYERS.write_text(json.dumps({**old, **layers}, indent=2, ensure_ascii=False) + "\n")
for k, v in results.items():
    print(f"{k:7} fooled {sum(r['fooled'] for r in v)}/12 | wrong decisions {sum(not r['decision']['match'] for r in v)}"
          f" | trap calls {sum(len(r['trap_calls']) for r in v)} | blocked {sum(len(r['blocked_tool_calls']) for r in v)}")
