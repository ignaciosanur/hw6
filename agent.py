"""Campus Customs vendor desk agent (entry point).

    python agent.py --doc data/practice_docs/p01_bluehen_quote.html                # all defenses
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html --no-defense   # Problem 3 agent
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html --layers code,prompt

Runs the agent on one vendor document, prints the report, and appends the run to
output/usage_log.json (tokens + dollars) and output/audit_trail.json (tool calls + answer).

Three defense layers, each can be switched on or off:
- code:   tools.load_document strips what a person can't see before any model reads it.
- design: code reads the document (no read tool to steer); the model only extracts facts;
          code makes the decision and writes the reason; send_email / approve_payment need
          human sign-off, so a model call to them is held and denied, never run.
- prompt: the security rules in prompts/prompt.md (off = prompts/prompt_no_defense.md).
"""
import argparse
import asyncio
import json
import os
import re
from collections import Counter
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, Tool, ToolDenied, UsageLimits, _utils
from pydantic_ai.messages import ModelResponse, ModelRequest, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage

import tools
from models import QuoteFacts, VendorReport

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

MODEL_NAME = "gpt-6-luna"  # the only model allowed in this homework
PROMPT = (ROOT / "prompts" / "prompt.md").read_text()                       # with security rules
PROMPT_NO_DEFENSE = (ROOT / "prompts" / "prompt_no_defense.md").read_text()  # original, for attack tests
HANDBOOK = (ROOT / "data" / "shop_handbook.md").read_text()
PRICES = json.loads((ROOT / "data" / "prices.json").read_text())[MODEL_NAME]
USAGE_LOG = tools.OUTPUT_DIR / "usage_log.json"
AUDIT_TRAIL = tools.OUTPUT_DIR / "audit_trail.json"


def build_model() -> OpenAIResponsesModel:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise SystemExit("PORTKEY_API_KEY is missing: copy .env.example to .env and put your Portkey key in it.")
    client = AsyncOpenAI(api_key=key, base_url=os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1"),
                         default_headers={"x-portkey-api-key": key})
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


LAYERS = ("code", "design", "prompt")
ALL_LAYERS, NO_LAYERS = frozenset(LAYERS), frozenset()
TOOLS = [tools.read_document, tools.send_email, tools.approve_payment]
# Design layer: no read tool (code reads the document) and the two dangerous tools are still
# registered, but each call needs a human's approval before it can run.
SIGNOFF_TOOLS = [Tool(tools.send_email, requires_approval=True), Tool(tools.approve_payment, requires_approval=True)]
_agents: dict[tuple[bool, bool, bool], Agent] = {}


def get_agent(prompt_layer: bool = True, design_layer: bool = True, cache: bool = True) -> Agent:
    """The prompt and the full handbook go out as the system instructions on every call.

    Without cache, the instructions start with a new random id on every request: OpenAI caches
    long prompts automatically even with no breakpoints, matching from the first token, so a
    prefix that differs on every request can never be read from cache.
    """
    key = (prompt_layer, design_layer, cache)
    if key not in _agents:
        instructions = f"{PROMPT if prompt_layer else PROMPT_NO_DEFENSE}\n\n# Campus Customs Shop Handbook\n\n{HANDBOOK}"
        if not cache:
            instructions = (lambda base: lambda: f"Request id: {uuid4().hex}\n\n{base}")(instructions)
        if design_layer:
            _agents[key] = Agent(build_model(), output_type=[QuoteFacts, DeferredToolRequests],
                                 deps_type=tools.DeskDeps, instructions=instructions, tools=SIGNOFF_TOOLS)
        else:
            _agents[key] = Agent(build_model(), output_type=VendorReport, deps_type=tools.DeskDeps,
                                 instructions=instructions, tools=TOOLS)
    return _agents[key]


# With cache: a breakpoint right after the stable instructions (prompt + handbook), so later
# calls read them at the cached rate. Without cache: explicit mode with no breakpoints, plus
# get_agent(cache=False)'s random prefix (explicit mode alone still showed automatic cache hits).
CACHE_SETTINGS = OpenAIResponsesModelSettings(
    openai_prompt_cache_options={"mode": "explicit", "ttl": "30m"}, openai_cache_instructions=True)
NO_CACHE_SETTINGS = OpenAIResponsesModelSettings(
    openai_prompt_cache_options={"mode": "explicit", "ttl": "30m"}, openai_cache_instructions=False)


def cost_usd(usage) -> dict:
    """Dollar cost from prices.json. input_tokens includes cache reads and writes."""
    uncached = usage.input_tokens - usage.cache_read_tokens - usage.cache_write_tokens
    parts = {
        "uncached_input": uncached * PRICES["input_per_1m"] / 1e6,
        "cached_input": usage.cache_read_tokens * PRICES["cached_input_per_1m"] / 1e6,
        "cache_write": usage.cache_write_tokens * PRICES["cache_write_per_1m"] / 1e6,
        "output": usage.output_tokens * PRICES["output_per_1m"] / 1e6,
    }
    return {**{k: round(v, 8) for k, v in parts.items()}, "total": round(sum(parts.values()), 8)}


def tool_calls(messages) -> list[dict]:
    """Pair every tool call with its return value, in order."""
    returns = {p.tool_call_id: p.content for m in messages if isinstance(m, ModelRequest)
               for p in m.parts if isinstance(p, ToolReturnPart)}
    calls = []
    for m in messages:
        if not isinstance(m, ModelResponse):
            continue
        for p in m.parts:
            if isinstance(p, ToolCallPart) and p.tool_call_id in returns:
                result = returns[p.tool_call_id]
                result = result.model_dump() if hasattr(result, "model_dump") else result
                short = json.dumps(result, default=str)
                calls.append({"tool": p.tool_name, "args": p.args_as_dict(),
                              "result": short[:200] + ("…" if len(short) > 200 else "")})
    return calls


def request_usage(messages) -> list[dict]:
    """Token counts the API reported for each model request in a run."""
    out = []
    for m in messages:
        if isinstance(m, ModelResponse):
            u = m.usage
            out.append({"input_tokens": u.input_tokens, "cached_tokens": u.cache_read_tokens,
                        "cache_write_tokens": u.cache_write_tokens, "output_tokens": u.output_tokens,
                        **{k: v for k, v in u.details.items()},
                        "cost_usd": cost_usd(u),
                        "cache_diagnostics": (m.provider_details or {}).get("prompt_cache_diagnostics")})
    return out


def decide(facts: QuoteFacts) -> tuple[VendorReport, list[str]]:
    """Design layer: code makes the decision and writes the reason from the handbook tables."""
    failed = tools.check_rules(facts.vendor, facts.sku, facts.unit_price, facts.lead_time_days, facts.min_order)
    if failed:
        decision, reason = "do_not_recommend", f"Do not recommend: it fails {' and '.join(failed)}."
    else:
        decision = "recommend"
        reason = (f"All four purchasing checks pass: {facts.vendor} is approved, ${facts.unit_price:.2f} is at or below the "
                  f"${tools.MAX_COST[facts.sku]:.2f} max unit cost, {facts.lead_time_days} days is within 21, "
                  f"and {facts.min_order} units is within 600.")
    return VendorReport(**facts.model_dump(), decision=decision, reason=reason), failed


DEFAULT_VOTES = 3  # design layer: extract the facts this many times at once and keep the majority per field
FACT_FIELDS = ("vendor", "sku", "unit_price", "lead_time_days", "min_order")


async def _run_once(agent: Agent, prompt: str | None, settings: dict, doc: str, blocked: list):
    """One agent run; a held sign-off call is logged, denied, and the model is let finish."""
    result = await agent.run(prompt, **settings)
    for _ in range(2):
        if not isinstance(result.output, DeferredToolRequests):
            break
        denials = {}
        for call in result.output.approvals:
            tools.log_blocked(doc, call.tool_name, call.args_as_dict())
            blocked.append({"tool": call.tool_name, "args": call.args_as_dict()})
            denials[call.tool_call_id] = ToolDenied("Blocked: this tool needs a human's sign-off. Do not retry. Return the facts.")
        result = await agent.run(message_history=result.all_messages(), usage=result.usage,
                                 deferred_tool_results=DeferredToolResults(approvals=denials), **settings)
    if isinstance(result.output, DeferredToolRequests):
        raise RuntimeError(f"{doc}: the model kept asking for sign-off tools")
    return result


def majority(facts: list[QuoteFacts]) -> QuoteFacts:
    """Per field, the value most extractions agree on (ties go to the earliest run)."""
    picked = {}
    for f in FACT_FIELDS:
        values = [getattr(x, f) for x in facts]
        counts = Counter(json.dumps(v) for v in values)
        best = max(counts.values())
        picked[f] = next(v for v in values if counts[json.dumps(v)] == best)
    return QuoteFacts(**picked)


def not_in_visible_text(facts: QuoteFacts, text: str) -> list[str]:
    """Facts the person-visible text doesn't literally contain (fine for a converted unit; worth a look otherwise)."""
    flat = text.replace(",", "")
    numbers = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", flat)}
    out = []
    if facts.sku and facts.sku not in text:
        out.append("sku")
    for f in ("unit_price", "lead_time_days", "min_order"):
        v = getattr(facts, f)
        if v is not None and float(v) not in numbers:
            out.append(f)
    if facts.vendor and facts.vendor.lower() not in text.lower():
        out.append("vendor")
    return out


def run(doc: str, cache: bool = True, defend: bool = True, layers: frozenset[str] | None = None,
        votes: int | None = None):
    """Run the agent on one document. Returns (report, run usage, per-request usage).

    defend=True means all three layers, False means none (the Problem 3 agent); `layers` picks any mix.
    With the design layer, the facts are extracted `votes` times (default 3) and the majority kept.
    """
    layers = frozenset(layers) if layers is not None else (ALL_LAYERS if defend else NO_LAYERS)
    deps = tools.DeskDeps(document=doc, sanitize="code" in layers)
    design = "design" in layers
    votes = (votes or DEFAULT_VOTES) if design else 1
    agent = get_agent("prompt" in layers, design, cache)
    settings = dict(deps=deps, usage_limits=UsageLimits(request_limit=6),
                    model_settings=CACHE_SETTINGS if cache else NO_CACHE_SETTINGS)
    blocked: list = []
    visible = None
    if design:  # code reads the document; the model never gets to choose what to open
        d = tools.load_document(doc, deps.sanitize, deps.removed)
        visible = d.text
        prompt = f"Vendor document `{doc}` ({d.file_type}), already read for you. Extract the facts.\n\n{d.text}"
    else:
        prompt = f"Vendor document path: {doc}"

    async def all_runs():
        return await asyncio.gather(*(_run_once(agent, prompt, settings, doc, blocked) for _ in range(votes)))

    # Same per-thread event loop that run_sync uses, so the model's HTTP client stays on one loop.
    results = _utils.get_event_loop().run_until_complete(all_runs())
    usage = RunUsage()
    for r in results:
        usage.incr(r.usage)
    messages = [m for r in results for m in r.all_messages()]
    if design:
        facts = majority([r.output for r in results])
        report, failed = decide(facts)
        check = {"decided_by": "code", "failed_checks": failed,
                 "votes": [r.output.model_dump() for r in results],
                 "unanimous": all(r.output == results[0].output for r in results),
                 "not_in_visible_text": not_in_visible_text(facts, visible)}
    else:
        report, check = results[0].output, None
    result = results[0]
    time = tools.now()
    tools.append_json(USAGE_LOG, {
        "document": doc,
        "time": time,
        "model": MODEL_NAME,
        "cache": cache,
        "defense_layers": sorted(layers),
        "requests": usage.requests,
        "tool_calls": usage.tool_calls,
        "input_tokens": usage.input_tokens,
        "cached_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.details.get("reasoning_tokens", 0),
        "total_tokens": usage.input_tokens + usage.output_tokens,
        "cost_usd": cost_usd(usage),
    })
    tools.append_json(AUDIT_TRAIL, {
        "document": doc,
        "time": time,
        "defense_layers": sorted(layers),
        "tool_calls": tool_calls(messages),
        "blocked_tool_calls": blocked,
        "hidden_content_removed": deps.removed,
        "rule_check": check,
        "final_answer": report.model_dump(),
    })
    return report, usage, request_usage(messages)


def main() -> None:
    parser = argparse.ArgumentParser(description="Campus Customs vendor desk agent")
    parser.add_argument("--doc", required=True, help="path to one vendor document (.html, .pdf, .eml)")
    parser.add_argument("--no-cache", action="store_true", help="turn prompt caching off")
    parser.add_argument("--no-defense", action="store_true", help="original undefended agent (for attack tests)")
    parser.add_argument("--layers", help="comma list of defense layers to use: code,design,prompt (default: all)")
    parser.add_argument("--votes", type=int, default=DEFAULT_VOTES, help="design layer: extractions to vote over (default 3)")
    args = parser.parse_args()
    layers = NO_LAYERS if args.no_defense else (
        frozenset(x.strip() for x in args.layers.split(",") if x.strip()) if args.layers else ALL_LAYERS)
    if unknown := layers - ALL_LAYERS:
        parser.error(f"unknown layer(s): {', '.join(sorted(unknown))}")
    report, usage, _ = run(args.doc, cache=not args.no_cache, layers=layers, votes=args.votes)
    print(report.model_dump_json(indent=2))
    c = cost_usd(usage)["total"]
    print(f"tokens: in {usage.input_tokens:,} (cached {usage.cache_read_tokens:,}) / out {usage.output_tokens:,}"
          f" | requests {usage.requests} | cost ${c:.6f}")


if __name__ == "__main__":
    main()
