"""Problem 8: run the final defended agent on the 10 exam documents. Results are written exactly
as the agent returns them (no hand edits).

    .venv/bin/python scripts/exam_run.py

Writes:
  output/exam_results.json  one entry per exam file, in the required fields
  output/exam_audit.json    per file: the 3 extraction votes, hidden text removed, sign-off calls
                            blocked, facts not found in the visible text, failed checks
  output/exam_results.md    a readable table of the same results
Each document is also logged to output/usage_log.json and output/audit_trail.json like any run.
Same thing per file:  python agent.py --doc data/exam_docs/e01_quote.html
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agent  # noqa: E402
import tools  # noqa: E402

DOCS = sorted(p for p in (ROOT / "data" / "exam_docs").iterdir() if p.suffix in (".html", ".pdf", ".eml"))
OUT = ROOT / "output"
results, audits = [], []
for doc in DOCS:
    rel = str(doc.relative_to(ROOT))
    report, usage, _ = agent.run(rel, layers=agent.ALL_LAYERS)
    traps = [t for t in json.loads(tools.TRAP_LOG.read_text() or "[]") if t.get("document") == rel]
    audit = next(a for a in reversed(json.loads(agent.AUDIT_TRAIL.read_text())) if a["document"] == rel)
    results.append({
        "file": doc.name,
        "vendor": report.vendor,
        "sku": report.sku,
        "unit_price": report.unit_price,
        "lead_time_days": report.lead_time_days,
        "min_order": report.min_order,
        "decision": report.decision,
        "reason": report.reason,
        "trap_tool_called": bool(traps),
        "input_tokens": usage.input_tokens,
        "cached_tokens": usage.cache_read_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": agent.cost_usd(usage)["total"],
    })
    audits.append({"file": doc.name, "votes": audit["rule_check"]["votes"], "unanimous": audit["rule_check"]["unanimous"],
                   "failed_checks": audit["rule_check"]["failed_checks"],
                   "not_in_visible_text": audit["rule_check"]["not_in_visible_text"],
                   "hidden_content_removed": audit["hidden_content_removed"],
                   "blocked_tool_calls": audit["blocked_tool_calls"], "trap_calls": traps,
                   "requests": usage.requests, "cache_write_tokens": usage.cache_write_tokens})
    r = results[-1]
    print(f"{doc.name:16} {r['vendor']:26} {r['sku']!s:10} ${r['unit_price']} {r['lead_time_days']}d min {r['min_order']}"
          f" -> {r['decision']:16} unanimous={audits[-1]['unanimous']} hidden={len(audits[-1]['hidden_content_removed'])}"
          f" unverified={audits[-1]['not_in_visible_text'] or '-'} ${r['cost_usd']:.6f}", flush=True)
    (OUT / "exam_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    (OUT / "exam_audit.json").write_text(json.dumps(audits, indent=2, ensure_ascii=False) + "\n")

L = ["# Problem 8: Exam Results\n",
     "The final defended agent (code + design + prompt layers, 3-vote fact extraction, gpt-6-luna) on all 10 documents in `data/exam_docs/`, "
     "written exactly as the agent returned them. Machine-readable: `output/exam_results.json`. Votes and evidence: `output/exam_audit.json`. "
     "Reproduce: `.venv/bin/python scripts/exam_run.py`.\n",
     "| File | Vendor | SKU | Unit price | Lead time (days) | Min order | Decision | Trap tool | Votes agreed | Hidden text removed | Cost |",
     "|---|---|---|---:|---:|---:|---|:-:|:-:|---|---:|"]
for r, a in zip(results, audits):
    hidden = "; ".join(h.split("]")[0].lstrip("[") for h in a["hidden_content_removed"] if not h.startswith("[email HTML")) or "none"
    L.append(f"| {r['file']} | {r['vendor']} | {r['sku']} | {r['unit_price']} | {r['lead_time_days']} | {r['min_order']} | **{r['decision']}** "
             f"| {'❌ yes' if r['trap_tool_called'] else '✅ no'} | {'✅' if a['unanimous'] else '⚠️ split'} | {hidden} | ${r['cost_usd']:.6f} |")
L.append("")
L.append("**Reasons**\n")
L += [f"- **{r['file']}**: {r['reason']}" for r in results]
L.append("")
tot = sum(r["cost_usd"] for r in results)
L.append(f"Totals: {sum(r['decision'] == 'recommend' for r in results)} recommend, {sum(r['decision'] == 'do_not_recommend' for r in results)} do_not_recommend; "
         f"trap tools called: {sum(r['trap_tool_called'] for r in results)}; sign-off calls blocked: {sum(len(a['blocked_tool_calls']) for a in audits)}; "
         f"total cost ${tot:.6f} (${tot / len(results):.6f} per document).")
(OUT / "exam_results.md").write_text("\n".join(L) + "\n")
print(f"wrote output/exam_results.json ({len(results)} files) | total ${tot:.6f}")
