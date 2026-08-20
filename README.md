# Argus

**One query. Every search engine. In parallel.**

Argus fans a single query out to up to five AI search/research providers at
once, lets you pick a fast `search` mode or a slower multi-step
`deep_research` mode per query, and hands back one combined report with a
built-in cost estimate — so you always know roughly what a query will cost
*before* you run it.

Named after [Argus Panoptes](https://en.wikipedia.org/wiki/Argus_Panoptes),
the all-seeing giant of Greek myth.

[![CI](https://github.com/sanchitmonga22/argus/actions/workflows/ci.yml/badge.svg)](https://github.com/sanchitmonga22/argus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

![OpenAI](https://img.shields.io/badge/OpenAI-412991?logoColor=white)
![Anthropic](https://img.shields.io/badge/Anthropic-D97757?logo=anthropic&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-8E75B2?logo=googlegemini&logoColor=white)
![Perplexity](https://img.shields.io/badge/Perplexity-1FB8CD?logo=perplexity&logoColor=white)
![Exa](https://img.shields.io/badge/Exa-000000?logoColor=white)

---

## How it works

```
                              ┌── Exa            (search | deep_research)
                              ├── Perplexity      (search | deep_research)
   "your query" ── fan out ── ├── OpenAI          (search | deep_research)
                              ├── Gemini          (search | deep_research)
                              └── Anthropic       (search | deep_research)
                                        │
                                        ▼
                        one combined report.md + results.json
                        + a per-provider, and total, cost estimate
```

Every provider runs in its own thread. One failing or slow provider never
blocks the others — Argus always returns whatever came back, with failures
called out separately in the report.

## Providers

| Provider | Search mode | Deep research mode | Cost |
|---|---|---|---|
| **Exa** | `search_and_contents(type="auto")` — fast ranked sources | `search_and_contents(type="deep-reasoning")` — slower, more thorough ranking | $7/1k requests · $15/1k for deep-reasoning |
| **Perplexity** | Agent API, `preset="low"` | Agent API, `preset="xhigh"` | $2-8/1M tokens + $5/1k requests |
| **OpenAI** | Responses API + `web_search` tool | `o3-deep-research` (background) | $1.25-10/1M in, up to $40/1M out |
| **Gemini** | Google Search grounding | Deep Research agent (background) | $1.50/$7.50 per 1M in/out + $14/1k grounded searches |
| **Anthropic** | `web_search` tool, single turn | `web_search` + `web_fetch`, multi-turn agentic loop | $10/1k searches + normal token cost |

Run `argus costs` any time for the full pricing table with sources, or
`argus costs --mode deep_research` for a live estimate scoped to whichever
providers you've configured. Pricing is a best-effort snapshot from each
provider's docs as of August 2026 — providers change pricing without notice,
so treat it as an estimate, not an invoice. See each provider's module in
`src/argus/providers/` for exact source links.

## Install

```bash
pip install "argus-research[all]"     # every provider's SDK
pip install "argus-research[exa,openai]"   # just the ones you use
```

Copy `.env.example` to `.env` and fill in whichever keys you have — one is
enough to get started:

```bash
cp .env.example .env
```

## CLI

```bash
argus providers                              # what's configured
argus costs                                  # static pricing table
argus costs --mode deep_research             # estimate for your configured keys

argus run "latest on-device LLM quantization techniques"
argus run "survey of transformer attention optimizations" \
  --mode deep_research --providers exa,anthropic --yes
argus run "..." --dry-run                    # print the cost estimate, call nothing
argus run "..." --json                       # machine-readable output
```

Every run prints a per-provider cost estimate before calling anything, and
(unless `--no-save`) writes `report.md`, `results.json`, and `metadata.json`
to `outputs/<timestamp>_<slug>/`.

## Python API

```python
from argus import Argus

agent = Argus()
print(agent.available_providers())          # only providers with a key set
print(agent.preflight_cost(mode="search"))  # {provider: (est_cost_usd, note)}

result = agent.research(
    "Qualcomm Hexagon HMX matrix multiply tile dimensions",
    mode="search",                    # or "deep_research"
    providers=["exa", "perplexity"],  # omit to use everything configured
)

print(result.to_markdown())     # combined report, all providers
print(result.total_cost_usd)    # summed estimate across providers
for r in result.succeeded:
    print(r.provider, r.model, r.cost_usd, len(r.sources))
```

## As a Claude / coding-agent skill

`skill/SKILL.md` packages the CLI above as a skill any Claude Code (or other
agent) session can install and use to research on your behalf — pip install,
add keys, call `argus run`. See that file for the full spec.

## Development

```bash
git clone https://github.com/sanchitmonga22/argus.git
cd argus
pip install -e ".[all,dev]"

ruff check src tests     # lint
mypy src                 # type-check
pytest                   # unit tests (no network, no API keys needed)

# opt-in, hits real APIs, needs keys in .env, costs a little money:
pytest tests/test_live_smoke.py -m live -v
```

CI (`.github/workflows/ci.yml`) runs lint + type-check + the unit test suite
on Python 3.10–3.13 for every push and PR. Live smoke tests are never run in
CI — they're for you to run locally once your `.env` is filled in.

## Project layout

```
src/argus/
├── core.py                    # Argus orchestrator + ArgusResult (combined report)
├── costs.py                   # pricing table + cost estimator
├── cli.py                     # `argus` command
└── providers/
    ├── base.py                # Provider / ProviderResult / Source / Mode
    ├── exa.py
    ├── perplexity.py
    ├── openai_provider.py
    ├── gemini.py
    └── anthropic_provider.py
tests/                         # unit tests (mocked) + opt-in live smoke tests
skill/SKILL.md                 # packages this as an agent-usable skill
```

## License

MIT — see [LICENSE](LICENSE).
