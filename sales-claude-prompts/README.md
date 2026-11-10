# Sales Claude Prompts

**Ten production-grade sales prompts for Claude — plus a CLI to run them.**

Each prompt is a carefully-engineered template with role priming, explicit input schemas, output contracts, and guardrails that keep the model from drifting into generic sales fluff. Point them at your deals, your transcripts, your pipeline, and get specific, named, actionable output — not "build more rapport."

---

## What's in the box

| # | Prompt | What it does |
|---|---|---|
| 01 | **ICP Definition** | Derive your real Ideal Customer Profile from your 10 closed-won deals, with disqualifiers and a scoring rubric. |
| 02 | **Discovery Questions** | 15 discovery questions grouped by Pain / Process / Power, starred by priority, with "what a good answer looks like." |
| 03 | **Objection Responses** | For any objection: short (≤35 word) response, long (≈100 word) response, confidence tier, and the re-frame to use. |
| 04 | **Cold Email Sequence** | A 5-touch cold sequence (Day 1, 4, 9, 15, 22). Each ≤75 words. No "I hope this finds you well." |
| 05 | **Follow-up Cadence** | 14-day post-demo cadence as a day-by-day table with the move, the channel, and the exit condition. |
| 06 | **Proposal Template** | Full proposal with executive summary, scope, pricing, risks — plus internal rep notes the buyer never sees. |
| 07 | **Call Debrief** | Reads a call transcript and returns 3 specific wins, 3 specific misses, subtext reads, and a deal health score. |
| 08 | **Pipeline Triage** | Weekly: categorize every open deal into Close-30 / Close-90 / Long-shot / Dead and name the 3 to fight for. |
| 09 | **Competitive Battle Card** | One-page battle card with trap-setting questions, honest "where they win" sections, and pricing gotchas. |
| 10 | **Account Research Briefing** | Pre-meeting one-pager: 3 priorities from public signals, 3 hypotheses to test, the one question that earns a second meeting. |

Each prompt lives in [prompts/](prompts/) as a self-contained markdown file. You can read them, edit them, fork them, run them through the CLI, or paste them straight into claude.ai.

---

## Why these are better than what you had

Most sales prompts floating around the internet are one-liners: *"Write a cold email to a VP of Sales about our product."* They produce LinkedIn-grade slop.

These prompts do five things differently:

1. **Role priming with teeth** — the system prompt gives the model a specific sales persona with specific pet peeves ("you never say 'circling back'"). Not "be a helpful sales assistant."
2. **Explicit input schemas** — every prompt declares its required inputs up front (e.g. `account_name`, `deal_size`, `transcript`). The CLI enforces them.
3. **Structured output contracts** — the prompt tells Claude exactly what sections to produce, in what order, with what length constraints. No wall-of-text responses.
4. **Guardrails against drift** — every prompt ends with a Guardrails section (what *not* to do, what *not* to invent, when to say "insufficient signal").
5. **Internal vs. buyer-facing split** — prompts like the proposal and battle card distinguish between what the rep uses internally and what the buyer actually sees.

---

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/kevinpaolocervantes/claude-for-sales-professionals.git
cd claude-for-sales-professionals/sales-claude-prompts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Set your API key:

```bash
cp .env.example .env
# then edit .env and paste your key
```

Or export it in your shell:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at [console.anthropic.com](https://console.anthropic.com/).

---

## Quick start

List all prompts:

```bash
python src/sales_claude.py list
```

Inspect one:

```bash
python src/sales_claude.py show 03
python src/sales_claude.py vars 03
```

Run one with inline inputs:

```bash
python src/sales_claude.py run 03 \
  --input objection="Your pricing is too high" \
  --input our_product="an AI-powered CRM" \
  --input buyer_role="VP of Sales" \
  --input deal_context="mid-market, 3-month cycle"
```

Run one with a long input from a file:

```bash
python src/sales_claude.py run 07 \
  --input deal_context="enterprise renewal, $450k ARR" \
  --input call_transcript=@./transcripts/acme-q3-call.txt
```

Run interactively (prompts you for each missing variable):

```bash
python src/sales_claude.py run 10 --interactive
```

Preview the rendered prompt without calling the API (free):

```bash
python src/sales_claude.py run 04 --input ... --dry-run
```

Save the output:

```bash
python src/sales_claude.py run 06 --input ... --save ./out/proposal-acme.md
```

---

## CLI reference

```
sales-claude list                 # table of all prompts
sales-claude show <id>            # print the full prompt markdown
sales-claude vars <id>            # list the variables a prompt expects
sales-claude run <id> [options]   # render + call the API
sales-claude render <id> [opts]   # just render, no API call
```

### `run` options

| Flag | What it does |
|---|---|
| `--input key=value` / `-i` | Pass a variable. Repeatable. Use `@path/to/file` to load a value from a file. |
| `--input-file inputs.json` / `-f` | Load all variables from a JSON object. |
| `--interactive` | Prompt for missing variables. Multi-line input via `:multi` ... `:end`. |
| `--model <id>` / `-m` | Override the model. Defaults to the prompt's own `Best model:` header, else `claude-opus-4-7`. |
| `--max-tokens N` | Default 4096. |
| `--stream` / `--no-stream` | Stream tokens as they arrive. Default: stream. |
| `--dry-run` | Render the prompt but don't call the API. Good for debugging and estimating cost. |
| `--save <path>` | Write the output to a file. |

### Prompt IDs

Any of these resolve to the same prompt:

- The number: `3`, `03`
- A substring of the filename: `objection`, `discovery`, `battlecard`

### A note on model selection

The CLI's default model is `claude-opus-4-7`. Each prompt file declares its own `Best model:` in the header, which takes precedence when you don't pass `--model`. If you want to force a specific model regardless of the prompt's suggestion, pass `--model claude-sonnet-4-7` (or whichever).

---

## Repository layout

```
sales-claude-prompts/
├── prompts/                  # the 10 prompt templates (markdown)
│   ├── 01_icp_definition.md
│   ├── 02_discovery_questions.md
│   ├── ...
│   └── 10_account_research_briefing.md
├── src/
│   └── sales_claude.py       # the CLI
├── examples/                 # sample input JSON files
├── tests/                    # (reserved)
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## Using the prompts without the CLI

Every prompt is just a markdown file. If you'd rather paste one into claude.ai or wire it up to your own agent, open the file, do a find-and-replace on the `{{variable}}` placeholders, and paste.

The `## System` section is intended to go in the `system` parameter if you're calling the API directly; the rest (`## Task`, `## Input`, etc.) goes in the user message. The CLI merges them into one user message for simplicity.

---

## Writing your own prompt

To add an 11th prompt, create `prompts/11_your_prompt.md` with this header:

```markdown
# Prompt 11 — Your Title

**Category:** Your category
**Best model:** `claude-opus-4-7`
**Inputs required:** `var_one`, `var_two`

---

## System

<role priming — be specific, give the model opinions>

## Task

<what you want it to do, using {{var_one}} and {{var_two}}>

## Input

- Variable one: **{{var_one}}**
- Variable two: **{{var_two}}**

## Output format

<explicit structure, length limits, section names>

## Guardrails

- What not to do
- What not to invent
- When to say "I don't have enough signal"
```

The CLI will pick it up on the next `list`.

---

## FAQ

**Does the model know anything about my company?**
No. The prompts are templates. You pass in your product, your ICP, your transcripts. Nothing is baked in.

**Is my data sent anywhere besides Anthropic?**
No. The CLI calls the Anthropic API directly. No analytics, no telemetry.

**Can I use this with Claude on Bedrock / Vertex?**
Not out of the box — the CLI uses the `anthropic` SDK with the public API. PRs welcome.

**Can I ship these to my reps?**
Yes. Fork the repo, replace the examples with your own, and lock the prompt files down. The CLI reads from `prompts/` relative to the repo, so you can keep the prompts in a shared location and distribute the CLI separately.

---

## Contributing

PRs welcome, especially:

- New prompts (follow the template above)
- Better default values and example inputs under `examples/`
- A Jupyter notebook demo
- A streamlit UI

---

## License

MIT. See [LICENSE](LICENSE).

---

*Built with Claude. If any prompt here saves you a two-hour meeting, send me a note.*
