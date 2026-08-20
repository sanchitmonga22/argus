---
name: argus-research
description: Search or deep-research the web through Exa, Perplexity, OpenAI, Gemini, and Claude in one call, with a built-in cost estimate. Use when the user asks to research a topic, compare answers across search providers, or wants an estimated cost before running a web search.
---

# Argus Research

Argus is a pip-installable CLI/Python package (`argus-research` on PyPI, repo:
https://github.com/sanchitmonga22/argus) that fans one query out to
up to five providers in parallel — Exa, Perplexity, OpenAI, Gemini, Anthropic
— in either a fast `search` mode or a slower, multi-step `deep_research` mode.

## Setup (once per machine)

```bash
pip install "argus-research[all]"
cp .env.example .env   # then fill in whichever API keys you have — one is enough
```

Only providers with a key present in the environment (or `.env`) activate;
others are skipped automatically.

## Using it

Check what's configured and what things cost before spending anything:

```bash
argus providers                    # which providers are configured
argus costs                        # static pricing table for every provider/mode
argus costs --mode deep_research   # rough per-provider estimate for your configured keys
```

Run a query:

```bash
argus run "latest advances in on-device LLM quantization" --mode search
argus run "comprehensive survey of transformer attention optimizations" \
  --mode deep_research --providers exa,anthropic --yes
```

`--dry-run` prints only the cost estimate and exits without calling any API —
use it first when the query might be expensive. `--json` prints the raw
result instead of the combined markdown report. Every run also writes
`report.md` / `results.json` / `metadata.json` to `outputs/<timestamp>_<slug>/`
unless `--no-save` is passed.

## From Python

```python
from argus import Argus

agent = Argus()
print(agent.available_providers())               # e.g. ["exa", "openai"]
print(agent.preflight_cost(mode="search"))        # {provider: (cost_usd, note)}

result = agent.research("your query", mode="search")
print(result.to_markdown())
print(result.total_cost_usd)
```

## When to reach for this

- The user wants one answer synthesized from multiple search/research APIs
  rather than picking one provider by hand.
- The user wants to know roughly what a search/deep-research call will cost
  before running it.
- The user is comparing providers (`argus run "..." --providers exa,openai`
  and diff the per-provider sections of the combined report).
