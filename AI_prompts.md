# AI Prompts

## Problem 1: Vibe coder prompts

### Initial prompt

> Create AI_prompts.md at the start of the assignment and keep it updated as we work. The file is the log of what we are typing to the vibe coder.
>
> Put one section for each problem. Each section must include:
>
> * The problem number and title
> * at least one prompt types
> * one follow-up prompt if it was needed (and one sentence on what was lacking after the first)

## Problem 2: Size up the handbook

### Initial prompt

> Unzip data.zip (if not done already) Look through data/shop_handbook.md
>
> this is the Campus Customs Shop Handbook, and our agent will send it to the model on every single call. Also look at data/prices.json, the gpt-6-luna price list.
>
> Find out how many tokens the handbook is. In output/handbook_estimate.md write:
>
> * the token count and how we got it
> * what the handbook alone costs in dollars on one call, and on 1K calls, with cached tokens and withouth then. Show the math (and do some descriptive stats tables please)
>
> We will check these estimates against real runs later on in problem 4

## Problem 3: Build the vendor desk agent

### Initial prompt

> Build the vendor desk agent with PydanticAI using gpt-6-luna The agent is these four files:
>
> * prompts/prompt.md (the instructions for the agent (the agent also sends the handbook to the model on every call)
> * agent.py (the entry point)
> * tools.py (the tools)
> * models.py (the structured types)
>
> Give the agent the opath to one vendor document. It reads the document with a tool (HTML, PDF, and .eml email files all have to work) and returns (vendor, SKU, unit price, lead time in days, minimum order, a decision (recommend or do_not_recommend) following the handbook rules, and a one-sentence reason
>
> The agent must also have two trap tools: send_email and approve_payment. Its job never needs them. They are there to catch a malicious document that tricks our agent into emailing someone or paying a vendor. They do not send or pay anything. They only append the call and its arguments to output/trap_calls.json (start it as an empty list), so if that file ever has an entry, a document took over your agent. Keep them in our system for the whole homework.
>
> After every run, append to:
>
> * output/usage_log.json: document, time, the token counts, the API reports, and the dollar cost using prices.json
> * output/audit_trail.json: each tool call with its arguments and a short result, plus the final answer
>
> Our agent should run like this in the terminal:
> python agent.py --doc data/practice_docs/p01_bluehen_quote.html
>
> What this is doing: runs our agent on one vendor quote and logs the answer, tools, and cost.
>
> Run it on p01 and p08 to show it works. Start output/harness.md: each filed in models.py and why, and each tool in one line

### Follow-up prompt

> To answer your questions:
>
> * add a defense
> * ok to run twice since that is what the problem is asking, no?
> * good to know caching is already working
> * it should be gpt-6-luna, not lune, so please correct it

What was lacking after the first prompt: the agent had no prompt-injection defense, and hidden text in 5 of the 12 practice documents changed its decision.

## Problem 4: With and without cached tokens

### Initial prompt

> The ahndbook is the same on every call, so the model can reuse it from a cache at a much cheaper price. Test what that is worth. Run our agent on all 12 practice documents in two ways:
>
> * with cache: set up so the handbook gets reused from cache
> * without cache: set up so nothing gets reused from cache
>
> Check the token counts the API sends back to prove each setup really did what we think. A without-cache run that still shows cached tokens does not count
>
> Save every model call from both setups to output/cache_test.json
>
> For each call include the setup, document, every token count the API reports, and dollars from prices.json
>
> in output/cache_test.md:
>
> * total cost and cost per document for each setup, and the percent that was saved
> * how our real numbers compare to probelm 2 estimate (add a graph)
> * A projection for 1,000 documents a day for 30 days, with and without cache
> * anything in the numers that its surprising, and why it happnes

## Problem 5: Attack your own agent

### Initial prompt

> Some vendor documents are booby-trapped with text aimed at AI. Run the Problem 3 agent, with no new defenses, on all 12 documents in data/pracitice_docs/ Compare each answer to data/practice_key.json and check output/trap_calls.json, the log your fake email and payment tools from Porblem 3 write to
>
> Save output/attack_results.json: for each document, whether each field matched the key, whether the decision matched, thether a trap tool was called, and whether a link or other strange text showed up in the answer.
>
> in output/attack_results.md, for every document that fooled your agent, write what fooled it and where in the file it was hiding. Open the documents the way a person would (browser, PDF viewer, email app) and compare that with what our agent read.

## Problem 6: Defend your agent

### Initial prompt

> Defend our agent at three levels:
>
> * Code: what you program does to the document before any model sees it
> * Design: how your agent is put together, so a poisoned document cannot reach the dangerous tools or the decision
> * Prompt: rules in "prompts/prompt.md"
>
> You may NOT delete send_email or approve_payment from our system. The shop will use them later with a human sign-off. Keep a way to run the agent with no defenseses, as we will need it for problem 7
>
> rerun all 12 practice documents. Save output/defense_results.json in the same shape as problem 5, plus tokens and dollars per document.
>
> Clean documents must still come back with the right values. Refusing or blanking out a real quote counts as a failure
>
> In output/defense_results.md
>
> * a before and after table for all 12 documents
> * what each layer catches that the others miss
> * the extra tokens and dollars each layer adds per document
>
> Add our safety features to output/harness.md in a Safety section: what each defense layer does, in plain words.

## Problem 7: Red team

### Initial prompt

> Now you are the attacker. Make two new booby-trapped vendor documents in data/my_attacks/ (HTML, PDF or email). each one should use a hiding trick or an attack goal that is not in the practice set.
>
> A person opening the document should see a normal quote.
>
> run both attacks on youra gent with no defenses and on your defended agent. In output/red_team.md for each attack: what is hidden, where, what it tries to make the agent do, and what happened before and after your defenses.
>
> more points for attacks that are new and that actually fool the agent with no defenses.

## Problem 8: Exam documents

### Initial prompt

> data/exams_docs/ has 10 vendor documents with no answer key. run your final defended agent on all of them. Do not hand-edit the results.
>
> Save output/exam_results.json with one entry per exam file. Each entry has these fields:
>
> * file: the exam file name, e.g., e01_quote.html
> * vendor
> * sku
> * unit_price
> * lead_time-days
> * min_order
> * decision: recommend or do_not_recommend
> * reason
> * trap_tool_called (true or false)
> * input_tokens, cached_tokens, output_tokens
> * cost_usd
>
> Graders will compare our results to a hidden asnwer key and rerun some agents to check. We get points for correct fiels and decision, no trap tool calls, and clean documents handled normally. please take your time, and be as smart as possible using all that we have learned through these homework assignemnts and lectures.

## Problem 9: Results page

### Initial prompt

> Build output/hw6_report.html
>
> it must be one file that opens by double-click with no internet and no other files next to it
>
> the page must show the five things below. Use our real numbers from ealier problems.
>
> * Our caching results, with a chart
> * Attacks before and after our defenses
> * What our defenses cost in tokens and dollars
> * Our exam results and our two read team attacks
> * A short recommendation to the store manager: should Campus Customs turn this agent on for real vendor mail, and what would it cost per month at 1,000 documents a day?
>
> More points for a designed page (fonts, color, layout) that reads well.
>
> The more designed the page (fonts, color, layout) that reads well, the more points we get, so please look for UX design tips online before implementing and don't make it look all Claude-like. Take inspo from other websites

## Problem 10: Push to GitHub and submit the URL

### Initial prompt

> Push our project to a public GitHub repository and give me a link so I can paste the URL on Canvas. Rememebr that graders will clone it, so make sure it opens and that the files below are there.
>
> Include the whole data/ folder (the course data plus our two attack files) so graders can clone our repo and run our agent right away. Do not commit my real .env
>
> use .gitignore to keep it out, and include .env.example with placeholders only
>
> the expected repo should look like the screenshot
>
> Other Python files are fine. Put a short note in README.md on how to run our agent
