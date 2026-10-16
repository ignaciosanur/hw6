# Homework 6: Campus Customs Vendor Desk (Tokenomics + Prompt Injection)

MGT 409, AI for Managers, Yale SOM, Fall 2026.

A PydanticAI agent on **gpt-6-luna** (via Portkey) that reads one vendor document (HTML, PDF, or `.eml`), extracts the vendor, SKU, unit price, lead time, and minimum order, and recommends whether Campus Customs should buy, following `data/shop_handbook.md`. It's defended against prompt injection at three layers: code, design, and prompt. The `send_email` and `approve_payment` tools are trap tools: they only write to `output/trap_calls.json`, and in the defended agent they need a human's sign-off.

**Start here:** open [`output/hw6_report.html`](output/hw6_report.html) (one self-contained page with the results).

## Run the agent

```bash
python3.14 -m venv .venv                      # Python 3.12+ works too
.venv/bin/pip install -r requirements.txt
cp .env.example .env                          # then put your PORTKEY_API_KEY in .env

.venv/bin/python agent.py --doc data/practice_docs/p01_bluehen_quote.html              # final defended agent
.venv/bin/python agent.py --doc data/exam_docs/e01_quote.html
.venv/bin/python agent.py --doc data/practice_docs/p02_elmcity_quote.html --no-defense # the undefended Problem 3 agent
```

Each run prints the report and the token cost, and appends to `output/usage_log.json` and `output/audit_trail.json`.

Other options:
- `--layers code,design,prompt` picks any mix of defense layers.
- `--votes 3` is the default: the facts are extracted 3 times and the majority kept.
- `--no-cache` turns prompt caching off.

## Re-run the homework

| Problem | Command | Output |
|---|---|---|
| 2 Handbook size and cost | `.venv/bin/python scripts/handbook_estimate.py` | `output/handbook_estimate.md` |
| 4 With vs. without cache | `scripts/cache_test.py`, then `scripts/cache_report.py` | `output/cache_test.{json,md,png}` |
| 5 Attack the agent | `scripts/attack_test.py`, `scripts/render_docs.py`, `scripts/attack_report.py` | `output/attack_results.{json,md}` |
| 6 Defenses | `scripts/defense_test.py`, then `scripts/defense_report.py` | `output/defense_results.{json,md}` |
| 7 Red team | `scripts/make_attacks.py`, `scripts/red_team_test.py`, `scripts/red_team_report.py` | `data/my_attacks/`, `output/red_team.md` |
| 8 Exam | `scripts/exam_run.py` | `output/exam_results.json` |
| 9 Results page | `scripts/build_report.py` | `output/hw6_report.html` |

Run each with `.venv/bin/python`. Scripts that call the model cost a few cents or less in total.

## Layout

- `agent.py`: the entry point. It builds the model, sets up the defense layers, decides in code, and writes the logs.
- `tools.py`: the document reader (with the code-layer cleaning), the trap tools, and the handbook rule checks.
- `models.py`: the structured types (`VendorReport`, `QuoteFacts`, `DocumentText`).
- `prompts/prompt.md`: the instructions with the security rules. `prompts/prompt_no_defense.md` is the original, used by `--no-defense`.
- `data/`: the course data (handbook, prices, practice docs and key, exam docs) plus `my_attacks/`, our two red-team documents and their answers.
- `output/`: every result, log, and report. `output/harness.md` documents the fields, the tools, and the Safety section.
- `AI_prompts.md`: the log of what we typed to the vibe coder, one section per problem.

`.env` is never committed. `.env.example` holds placeholders only.
