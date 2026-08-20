"""
Cost calculator for every provider/mode Argus supports.

Numbers below are best-effort snapshots of published pricing as of
August 2026 (see README for source links) — providers change pricing
without notice, so treat `estimate()` as an approximation, not an invoice.
Where a provider doesn't publish a flat rate (e.g. Exa's async Research
API, Gemini's Deep Research agent), we compute from token/request usage
when available and otherwise return `cost_usd=None` with a `cost_note`
explaining why.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Price:
    input_per_1m: float = 0.0
    output_per_1m: float = 0.0
    per_1k_requests: float = 0.0   # flat fee per call, on top of token costs
    note: str = ""


# provider -> mode -> Price
PRICING: dict[str, dict[str, Price]] = {
    "exa": {
        "search": Price(per_1k_requests=7.0, note="type=auto, <=10 results"),
        "deep_research": Price(per_1k_requests=15.0, note="type=deep-reasoning; Exa's old standalone Research agent was retired in 2026"),
    },
    "perplexity": {
        "search": Price(per_1k_requests=5.0, note="raw Search API, snippets only, no tokens billed"),
        "deep_research": Price(
            input_per_1m=2.0, output_per_1m=8.0, per_1k_requests=5.0,
            note="sonar-deep-research equiv. (Agent API preset=high); citation/reasoning tokens billed separately at $2-3/1M",
        ),
    },
    "openai": {
        "search": Price(input_per_1m=1.25, output_per_1m=10.0, per_1k_requests=10.0, note="gpt-5-search-api + web_search tool"),
        "deep_research": Price(input_per_1m=10.0, output_per_1m=40.0, note="o3-deep-research (o4-mini-deep-research is ~5x cheaper)"),
    },
    "gemini": {
        "search": Price(input_per_1m=1.50, output_per_1m=7.50, per_1k_requests=14.0, note="gemini-3.6-flash + Google Search grounding; first 5,000 grounded prompts/month free"),
        "deep_research": Price(note="no fixed rate published as of Aug 2026; Google's own rough estimate is ~$1-3/task (Deep Research) or ~$3-7/task (Deep Research Max), billed at standard token rates"),
    },
    "anthropic": {
        "search": Price(per_1k_requests=10.0, note="web_search tool call fee; plus normal token cost for the calling model"),
        "deep_research": Price(per_1k_requests=10.0, note="agentic search+fetch loop; fee is per web_search call, N calls per run"),
    },
}


def estimate(provider: str, mode: str, usage: dict | None = None) -> tuple[float | None, str]:
    """
    Return (cost_usd, note). cost_usd is None when we can't compute a
    number from `usage` and there is no flat per-request price to fall
    back on.

    `usage` keys we understand (all optional): input_tokens, output_tokens,
    requests (defaults to 1), searches (defaults to `requests` when unset).
    """
    price = PRICING.get(provider, {}).get(mode)
    if price is None:
        return None, "no pricing data for this provider/mode"

    usage = usage or {}
    requests = usage.get("requests", 1)
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    cost = 0.0
    have_number = False

    if price.per_1k_requests:
        cost += price.per_1k_requests * requests / 1000
        have_number = True
    if price.input_per_1m and input_tokens:
        cost += price.input_per_1m * input_tokens / 1_000_000
        have_number = True
    if price.output_per_1m and output_tokens:
        cost += price.output_per_1m * output_tokens / 1_000_000
        have_number = True

    if not have_number:
        return None, price.note or "usage-metered — see raw API response for actual cost"

    return round(cost, 6), price.note


# Rough token assumptions used for the *pre-flight* estimate shown before a
# call is made (i.e. before we know real usage). Deliberately conservative
# (biased toward the higher end) so the number is a ceiling, not a lure.
_TYPICAL_USAGE = {
    "search": {"requests": 1, "input_tokens": 1_500, "output_tokens": 1_500},
    "deep_research": {"requests": 1, "input_tokens": 4_000, "output_tokens": 12_000},
}


def preflight_estimate(provider: str, mode: str) -> tuple[float | None, str]:
    """
    Rough "what will this roughly cost?" figure computed BEFORE the call is
    made, using typical token assumptions rather than real usage. Use
    `estimate()` with real usage afterwards for the actual figure.
    """
    cost, note = estimate(provider, mode, _TYPICAL_USAGE.get(mode))
    if cost is None:
        return None, note
    return cost, f"~estimate based on typical usage, not exact — {note}"


def table() -> str:
    """Render a human-readable cost table for `argus costs`."""
    lines = [
        f"{'provider':<12} {'mode':<14} {'in $/1M':>9} {'out $/1M':>9} {'per 1k req':>11}  note",
        "-" * 100,
    ]
    for provider, modes in PRICING.items():
        for mode, price in modes.items():
            lines.append(
                f"{provider:<12} {mode:<14} "
                f"{price.input_per_1m:>9.2f} {price.output_per_1m:>9.2f} "
                f"{price.per_1k_requests:>11.2f}  {price.note}"
            )
    return "\n".join(lines)
