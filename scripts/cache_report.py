"""Problem 4: build output/cache_test.md and output/cache_test.png from output/cache_test.json.

    .venv/bin/python scripts/cache_report.py
"""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib
import tiktoken

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CALLS = json.loads((ROOT / "output" / "cache_test.json").read_text())
PRICES = json.loads((ROOT / "data" / "prices.json").read_text())["gpt-6-luna"]
P_IN, P_READ, P_WRITE, P_OUT = (PRICES[k] / 1e6 for k in
                                ("input_per_1m", "cached_input_per_1m", "cache_write_per_1m", "output_per_1m"))
HB = len(tiktoken.get_encoding("o200k_base").encode((ROOT / "data" / "shop_handbook.md").read_text()))
OUT_MD, OUT_PNG = ROOT / "output" / "cache_test.md", ROOT / "output" / "cache_test.png"
SETUPS = [("without_cache", "Without cache"), ("with_cache", "With cache")]
BLUE, ORANGE, AQUA, INK, MUTED, GRID, SURFACE = "#2a78d6", "#eb6834", "#1baf7a", "#1f1f1e", "#6b6a63", "#e6e5df", "#fcfcfb"

by = {s: [c for c in CALLS if c["setup"] == s] for s, _ in SETUPS}
assert all(len(v) for v in by.values()), "run scripts/cache_test.py for both setups first"


def total(calls, f):
    return sum(c["cost_usd"]["total"] if f == "cost" else c[f] for c in calls)


def per_doc(calls):
    d = defaultdict(list)
    for c in calls:
        d[c["document"]].append(c)
    return d


stats = {}
for s, _ in SETUPS:
    calls, docs = by[s], per_doc(by[s])
    doc_costs = [total(v, "cost") for v in docs.values()]
    stats[s] = dict(
        calls=len(calls), docs=len(docs), cost=total(calls, "cost"), per_doc=total(calls, "cost") / len(docs),
        input=total(calls, "input_tokens"), cached=total(calls, "cached_tokens"),
        write=total(calls, "cache_write_tokens"), output=total(calls, "output_tokens"),
        reasoning=sum(c.get("reasoning_tokens", 0) for c in calls),
        hits=sum(c["cached_tokens"] > 0 for c in calls),
        in_per_call=total(calls, "input_tokens") / len(calls),
        doc_costs=doc_costs, decisions=sum(v[0]["decision_correct"] for v in docs.values()),
        parts={k: sum(c["cost_usd"][k] for c in calls) for k in ("uncached_input", "cached_input", "cache_write", "output")},
    )
nc, wc = stats["without_cache"], stats["with_cache"]
saved = 1 - wc["cost"] / nc["cost"]

# Problem 2 estimates (handbook only, one send per document).
est_nc, est_write, est_read = HB * P_IN, HB * P_WRITE, HB * P_READ
reqs_per_doc = nc["calls"] / nc["docs"]


def usd(x, d=6):
    return f"{'−' if x < 0 else ''}${abs(x):,.{d}f}"


L = []
w = L.append
w("# Problem 4: With and Without Cached Tokens\n")
w("Our vendor desk agent ran on all 12 practice documents twice, once **with** prompt caching and once **without**. "
  f"Every model call ({nc['calls']} + {wc['calls']} = {nc['calls'] + wc['calls']}) is saved in `output/cache_test.json` "
  "with its setup, document, every token count the API reported, and dollars from `data/prices.json`.\n")
w("Reproduce: `.venv/bin/python scripts/cache_test.py` (runs the agent; costs real tokens), then "
  "`.venv/bin/python scripts/cache_report.py` (rebuilds this page and the chart from the JSON).\n")

w("## The two setups, and proof each did what we think\n")
w("| Setup | How it's configured | What the API reported | Verdict |\n|---|---|---|---|")
w(f"| **With cache** | `prompt_cache_options = {{mode: explicit, ttl: 30m}}` plus `openai_cache_instructions=True`: one cache breakpoint right after the stable prefix "
  f"(`prompt.md` + the full handbook). The document and the conversation come after it. | **{wc['cached']:,} cached tokens** read across "
  f"{wc['hits']} of {wc['calls']} calls | ✅ handbook reused from cache |")
w(f"| **Without cache** | Explicit mode with **no** breakpoints (turns off OpenAI's implicit one), **and** a random `Request id` at the very start "
  f"of the instructions on every request, so no prefix can ever match a stored one. | **{nc['cached']:,} cached tokens** on all {nc['calls']} calls | ✅ nothing reused |")
w("")
w("> **Why the random id was needed:** our first no-cache attempt used explicit mode with zero breakpoints (we checked the outgoing request body). "
  "The API still reported cache reads of about 10.5K tokens on half the calls, because OpenAI caches long prompts automatically. "
  "Per the assignment, a no-cache run with cached tokens doesn't count, so we threw that run out and re-ran with a prefix that changes on every request.\n")

w("## 1. Cost: totals, per document, and savings\n")
w("| | Without cache | With cache | Difference |\n|---|---:|---:|---:|")
rows = [("Documents", nc["docs"], wc["docs"], None), ("Model calls (requests)", nc["calls"], wc["calls"], None),
        ("Input tokens", nc["input"], wc["input"], None), ("… read from cache", nc["cached"], wc["cached"], None),
        ("… written to cache", nc["write"], wc["write"], None), ("Output tokens", nc["output"], wc["output"], None),
        ("… of which reasoning", nc["reasoning"], wc["reasoning"], None)]
for name, a, b, _ in rows:
    w(f"| {name} | {a:,} | {b:,} | {b - a:+,} |")
w(f"| **Total cost** | **{usd(nc['cost'])}** | **{usd(wc['cost'])}** | **{usd(wc['cost'] - nc['cost'])}** |")
w(f"| **Cost per document** | **{usd(nc['per_doc'])}** | **{usd(wc['per_doc'])}** | **{usd(wc['per_doc'] - nc['per_doc'])}** |")
w(f"| **Saved by caching** | | | **{saved:.1%}** |\n")

w("### Where the dollars went\n")
w("| Cost component | Rate / 1M | Without cache | With cache |\n|---|---:|---:|---:|")
for k, label, rate in [("uncached_input", "Uncached input", P_IN), ("cached_input", "Cached input (read)", P_READ),
                       ("cache_write", "Cache write", P_WRITE), ("output", "Output", P_OUT)]:
    w(f"| {label} | ${rate * 1e6:.3f} | {usd(nc['parts'][k])} ({nc['parts'][k] / nc['cost']:.0%}) | {usd(wc['parts'][k])} ({wc['parts'][k] / wc['cost']:.0%}) |")
w("")

w("### Per document\n")
w("| Document | Without cache | With cache | Saved | Cached tokens (with cache) |\n|---|---:|---:|---:|---:|")
dn, dw = per_doc(by["without_cache"]), per_doc(by["with_cache"])
for doc in sorted(dn):
    a, b = total(dn[doc], "cost"), total(dw[doc], "cost")
    w(f"| {doc} | {usd(a)} | {usd(b)} | {1 - b / a:.0%} | {total(dw[doc], 'cached_tokens'):,} |")
w("")
w("| Cost-per-document statistic | Without cache | With cache |\n|---|---:|---:|")
for name, fn in [("Mean", st.mean), ("Median", st.median), ("Min", min), ("Max", max), ("Std. dev.", st.pstdev)]:
    w(f"| {name} | {usd(fn(nc['doc_costs']))} | {usd(fn(wc['doc_costs']))} |")
w("")

w("## 2. Real numbers vs the Problem 2 estimate\n")
w(f"Problem 2 priced only the handbook ({HB:,} tokens, counted with tiktoken), sent **once** per document.\n")
w("| Quantity | Problem 2 estimate | Actual | Actual ÷ estimate |\n|---|---:|---:|---:|")
w(f"| Input tokens per model call | {HB:,} (handbook only) | {nc['in_per_call']:,.0f} | {nc['in_per_call'] / HB:.2f}× |")
w(f"| Model calls per document | 1 | {reqs_per_doc:.0f} | {reqs_per_doc:.0f}× |")
w(f"| Input tokens per document | {HB:,} | {nc['input'] / nc['docs']:,.0f} | {nc['input'] / nc['docs'] / HB:.2f}× |")
w(f"| Cost per document, without cache | {usd(est_nc)} | {usd(nc['per_doc'])} | {nc['per_doc'] / est_nc:.2f}× |")
w(f"| Cost per document, with cache (warm: all reads) | {usd(est_read)} | {usd(wc['per_doc'])} | {wc['per_doc'] / est_read:.2f}× |")
w(f"| 1,000 documents, without cache | {usd(1000 * est_nc, 2)} | {usd(1000 * nc['per_doc'], 2)} | {nc['per_doc'] / est_nc:.2f}× |")
w(f"| 1,000 documents, with cache | {usd(est_write + 999 * est_read, 2)} | {usd(1000 * wc['per_doc'], 2)} | {wc['per_doc'] * 1000 / (est_write + 999 * est_read):.2f}× |")
w(f"| Saving from caching | 89.9% | {saved:.1%} | |")
w("")
w("![Problem 2 estimate vs real cost per document](cache_test.png)\n")
w(f"**What explains the gap:** the tokenizer count was close. Each call carries {nc['in_per_call'] - HB:,.0f} tokens beyond the handbook "
  f"(`prompt.md`, the tool schemas, the document, message framing), only {nc['in_per_call'] / HB - 1:.0%} more. "
  f"The big miss is the **{reqs_per_doc:.0f} model calls per document** (one to call `read_document`, one to answer). That sends the handbook twice, "
  "and the cost per document roughly doubles with it.\n")

w("## 3. Projection: 1,000 documents a day for 30 days\n")
N = 30_000
w(f"30 days × 1,000 documents = **{N:,} documents**, priced at the real cost per document measured above.\n")
w("| Setup | Cost per document | Per day (1,000 docs) | 30 days |\n|---|---:|---:|---:|")
w(f"| Without cache | {usd(nc['per_doc'])} | {usd(1000 * nc['per_doc'], 2)} | **{usd(N * nc['per_doc'], 2)}** |")
w(f"| With cache (as measured here) | {usd(wc['per_doc'])} | {usd(1000 * wc['per_doc'], 2)} | **{usd(N * wc['per_doc'], 2)}** |")
warm = wc["per_doc"]
w(f"| **Saved** | {usd(nc['per_doc'] - warm)} | {usd(1000 * (nc['per_doc'] - warm), 2)} | **{usd(N * (nc['per_doc'] - warm), 2)} ({saved:.0%})** |")
# Best case: every call reads the full stable prefix.
stable = st.median(c["cached_tokens"] for c in by["with_cache"] if c["cached_tokens"] > 0)
per_call_best = stable * P_READ + (wc["in_per_call"] - stable) * P_IN + (wc["output"] / wc["calls"]) * P_OUT
best_doc = per_call_best * reqs_per_doc
w(f"| With cache, every call a hit (best case) | {usd(best_doc)} | {usd(1000 * best_doc, 2)} | {usd(N * best_doc, 2)} |")
w("")
w(f"At 1,000 documents a day (one every ~86 seconds over a 24-hour day, far more often over a workday) the cache never sits idle for its 30-minute TTL. "
  "So in steady production the bill should fall between the measured and best-case rows, if the routing misses we saw (surprise 2) shrink with traffic. "
  f"Caching is worth about {usd(N * (nc['per_doc'] - warm), 0)} a month at the hit rate we measured, and up to "
  f"{usd(N * (nc['per_doc'] - best_doc), 0)} a month if every call hits.\n")

w("## 4. What's surprising in the numbers, and why\n")
nc_write_share = nc["parts"]["cache_write"] / nc["cost"]
w(f"1. **\"Without cache\" still pays the cache-write premium.** No call read a single cached token, yet the API reported "
  f"{nc['write']:,} **cache-write** tokens ({nc['write'] / nc['input']:.0%} of input), billed at $0.125/1M instead of $0.10. "
  "OpenAI stores long prompts automatically whether or not anything reuses them. A unique prefix stops the reads but not the writes. "
  f"That's why the no-cache bill is {nc_write_share:.0%} cache writes and lands above Problem 2's plain-input estimate. "
  "Turning caching \"off\" makes the bill **worse** than never having caching at all.")
miss = [c for c in by["with_cache"] if c["cached_tokens"] == 0]
long_reads = [c for c in by["with_cache"] if c["cached_tokens"] > 10_600]
w(f"2. **With cache, {len(miss)} of {wc['calls']} calls still missed, often seconds after a hit on the same prefix.** "
  "Caching is best-effort. Our run kept alternating: request 1 of a document reads about 10.5K cached tokens, then request 2 of the *same* document, "
  "seconds later, reads 0 and rewrites about 10.7K at the 1.25× rate. A cache only helps the server that holds it, so this looks like our requests "
  "being spread across servers (and possibly across OpenAI backends behind the Portkey gateway; we can't see that). "
  "We tried a fixed `prompt_cache_key`, OpenAI's tool for routing similar requests to the same cache, on 4 documents. "
  "It did not help (2 of 4 documents still missed on both calls), so we left it out. "
  f"Each miss costs about 10× a hit, which is why the measured saving ({saved:.0%}) falls well short of Problem 2's 90%.")
w(f"3. **Cache reads come in more than one size.** Most hits read about 10,516 to 10,536 tokens, the stable prefix (prompt + handbook) up to our breakpoint. "
  f"But {len(long_reads)} calls read about 10,680 to 10,720, i.e. the whole previous request including the tool call. "
  "So OpenAI also caches at the end of a request, even in explicit mode. Whatever comes after the cached part (the document, the new turn) bills at the normal input rate.")
w(f"4. **The second call per document is the hidden doubler.** The model needs one call to ask for `read_document` and another to answer. "
  "Both carry the full handbook. Reading the document in code and passing it in up front would halve the calls, a lever for later problems.")
w(f"5. **Output is tiny but not free.** About {wc['output'] / wc['docs']:,.0f} output tokens per document "
  f"({wc['reasoning'] / max(wc['output'], 1):.0%} of them hidden reasoning) cost 5× input per token. "
  f"With caching, output is {wc['parts']['output'] / wc['cost']:.0%} of the bill, so once input is cheap, short answers matter.")
w(f"6. **The answers aren't a caching story: {nc['decisions']}/12 decisions right without cache, {wc['decisions']}/12 with cache.** "
  "The difference is p03, where the model happened to resist the injection on one run and not the other. The same input doesn't always give the same answer. "
  "The wrong ones are not caching bugs. The baseline agent fell for prompt injections hidden in those documents (fake lower prices, fake lead times, a fake vendor name). "
  "That's the safety half of this homework. These cost runs used the original, undefended agent "
  "(`python agent.py --no-defense`). The defense added afterwards changes the prompt slightly, but not the cost picture.")

OUT_MD.write_text("\n".join(L) + "\n")

# ---- chart: small multiples, one shared measure per panel -------------------
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"wspace": 0.28})
series = [("Problem 2 estimate (handbook, 1 send)", BLUE), ("Problem 2 estimate × 2 calls", AQUA), ("Actual (all tokens)", ORANGE)]
groups = ["Without cache", "With cache"]
cost_vals = [[est_nc * 1e3, est_read * 1e3], [2 * est_nc * 1e3, 2 * est_read * 1e3], [nc["per_doc"] * 1e3, wc["per_doc"] * 1e3]]
tok_vals = [[HB, HB], [2 * HB, 2 * HB], [nc["input"] / nc["docs"], wc["input"] / wc["docs"]]]
bw = 0.26
for ax, vals, title, fmt in [(axes[0], cost_vals, "Cost per document (tenths of a cent = $0.001)", "{:.2f}"),
                             (axes[1], tok_vals, "Input tokens per document", "{:,.0f}")]:
    for i, ((name, color), v) in enumerate(zip(series, vals)):
        xs = [g + (i - 1) * (bw + 0.02) for g in range(len(groups))]
        bars = ax.bar(xs, v, bw, color=color, label=name, edgecolor=SURFACE, linewidth=2)
        for b, val in zip(bars, v):
            ax.annotate(fmt.format(val), (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom",
                        fontsize=8.5, color=INK, xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(range(len(groups)), groups, color=INK)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
axes[0].set_ylabel("$ per document × 1,000  (i.e. tenths of a cent)")
axes[1].set_ylabel("tokens")
fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=3, frameon=False, fontsize=9,
           bbox_to_anchor=(0.5, 1.02), labelcolor=INK)
fig.suptitle("Problem 2 estimate vs real runs, 12 practice documents, gpt-6-luna", y=1.09, color=INK, fontsize=12, x=0.5)
fig.savefig(OUT_PNG, dpi=160, bbox_inches="tight")
print(f"wrote {OUT_MD.relative_to(ROOT)} and {OUT_PNG.relative_to(ROOT)} | without ${nc['cost']:.6f} with ${wc['cost']:.6f} saved {saved:.1%}")
