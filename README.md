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
| **Exa** | `search(type="auto")` — fast ranked sources | `search(type="deep-reasoning")` — slower, more thorough ranking | $7/1k requests · $15/1k for deep-reasoning |
| **Perplexity** | Agent API, `preset="low"` | Agent API, `preset="xhigh"` | ~$3-15/1M tokens + $5-10/1k requests |
| **OpenAI** | Responses API + `web_search` tool | `o3-deep-research` (background) | $1.25-10/1M in, up to $40/1M out + $10/1k searches |
| **Gemini** | Google Search grounding | Deep Research agent (background) | $1.50/$7.50 per 1M in/out + $14/1k search queries |
| **Anthropic** | `web_search` tool, single turn | `web_search` + `web_fetch`, multi-turn agentic loop | $3/$15 per 1M tokens + $10/1k searches |

`argus` always distinguishes **per-request** fees (Exa, Perplexity's raw
Search API — one call is always one billable unit) from **per-search** fees
(OpenAI, Gemini, Anthropic — a single call can trigger zero, one, or many
searches server-side, so the real count is read back from each provider's
own response and billed accordingly, not assumed to be one).

Run `argus costs` any time for the full pricing table, or `argus costs
--mode deep_research` for a live pre-flight estimate scoped to whichever
providers you've configured — every `argus run` also prints this estimate
before calling anything, and the *actual* per-provider cost (computed from
real token/search counts returned by each API) in the final report.

### Where these numbers come from

Pricing is a best-effort snapshot of each provider's own published docs,
verified directly (not via third-party aggregators) as of **August 20,
2026** — providers change pricing without notice, so treat every figure as
an estimate, not an invoice. Exact source pages:

| Provider | Pricing page | API reference used |
|---|---|---|
| Exa | [exa.ai/docs/reference/pricing](https://exa.ai/docs/reference/pricing) | [exa.ai/docs/reference/search-api-guide](https://exa.ai/docs/reference/search-api-guide) — search() returns an exact `cost_dollars.total` per call, used in place of the static estimate whenever present |
| Perplexity | [docs.perplexity.ai/getting-started/pricing](https://docs.perplexity.ai/getting-started/pricing) | [docs.perplexity.ai/docs/agent-api/quickstart](https://docs.perplexity.ai/docs/agent-api/quickstart), [.../agent-api/presets](https://docs.perplexity.ai/docs/agent-api/presets), [.../agent-api/migrate-from-sonar/overview](https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar/overview) (preset→legacy-model mapping used to proxy Agent API pricing — not independently published), [.../search/quickstart](https://docs.perplexity.ai/docs/search/quickstart) (raw Search API, $5/1k requests, not currently used by this package's `search` mode) |
| OpenAI | [developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing) | [.../guides/tools-web-search](https://developers.openai.com/api/docs/guides/tools-web-search), [.../guides/deep-research](https://developers.openai.com/api/docs/guides/deep-research), [.../models/o3-deep-research](https://developers.openai.com/api/docs/models/o3-deep-research), [.../models/o4-mini-deep-research](https://developers.openai.com/api/docs/models/o4-mini-deep-research) |
| Gemini | [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing) | [.../docs/models](https://ai.google.dev/gemini-api/docs/models), [.../docs/google-search](https://ai.google.dev/gemini-api/docs/google-search), [.../docs/deep-research](https://ai.google.dev/gemini-api/docs/deep-research) |
| Anthropic | [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing) | [.../agents-and-tools/tool-use/web-search-tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool) ($10/1k search fee), [.../agents-and-tools/tool-use/web-fetch-tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool) |

Anthropic's Claude Sonnet 5 is currently at **intro pricing** ($2/$10 per 1M
input/output tokens through 2026-08-31, standard rate $3/$15 after) — this
package prices at the $3/$15 standard rate so estimates don't understate
cost once the intro window ends.

## Install

Not on PyPI yet — install straight from GitHub (always tracks the latest commit on `main`):

```bash
pip install "argus-research[all] @ git+https://github.com/sanchitmonga22/argus.git"
```

Or pin to a specific tagged release's wheel from the [Releases page](https://github.com/sanchitmonga22/argus/releases) — e.g. for v0.1.1:

```bash
pip install "https://github.com/sanchitmonga22/argus/releases/download/v0.1.1/argus_research-0.1.1-py3-none-any.whl[all]"
```

`[all]` pulls in every provider's SDK; swap in just the ones you use, e.g. `[exa,openai]`.

## Onboarding — set up your API keys once

```bash
argus init
```

Walks you through each provider (with a link to get a key), one is enough
to get started. Keys are saved to `~/.config/argus/.env` (`%APPDATA%\argus\
.env` on Windows), permissioned owner-read/write only, and picked up
automatically by `argus` from **any directory afterward** — no per-project
setup, no shell profile edits. Run it again any time to add or replace a
key. If a key is already sitting in your shell environment, `init` offers
to save it into this file too.

Precedence when multiple sources are set (highest wins): real environment
variables → `./.env` in the current directory (project-local override) →
`~/.config/argus/.env` (the global file `init` writes). `argus providers`
shows exactly which of the three each configured key is coming from.

Prefer to manage it yourself instead of the wizard? Copy `.env.example` to
`.env` in whichever directory you run `argus` from — same effect for that
project.

## CLI

```bash
argus init                                   # one-time: configure & save API keys
argus providers                              # what's configured, and where each key came from
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
