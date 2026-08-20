from argus.costs import PRICING, estimate, preflight_estimate, table


def test_estimate_flat_per_request_fee() -> None:
    cost, note = estimate("exa", "search", {"requests": 1})
    assert cost == 0.007  # $7 / 1000 requests
    assert "auto" in note.lower() or note


def test_estimate_token_based() -> None:
    cost, _ = estimate("openai", "search", {"input_tokens": 1_000_000, "output_tokens": 1_000_000})
    assert cost == 1.25 + 10.00  # tokens only — no searches reported, so no search fee


def test_estimate_charges_per_search_not_per_request() -> None:
    # OpenAI's web_search fee is per actual search invocation, not per API call —
    # a request that made 3 searches should be billed for 3, not 1.
    cost, _ = estimate("openai", "search", {"searches": 3})
    assert cost == 10.0 * 3 / 1000


def test_estimate_zero_searches_means_no_search_fee() -> None:
    cost, _ = estimate("openai", "search", {"input_tokens": 100, "output_tokens": 100, "searches": 0})
    assert cost is not None and cost < 0.005  # only trivial token cost, no $10/1k fee applied


def test_estimate_unknown_provider_returns_none() -> None:
    cost, note = estimate("not-a-real-provider", "search")
    assert cost is None
    assert "no pricing data" in note


def test_estimate_usage_metered_mode_without_usage_returns_none() -> None:
    cost, note = estimate("gemini", "deep_research", {})
    assert cost is None
    assert note


def test_preflight_estimate_is_labelled_as_rough() -> None:
    cost, note = preflight_estimate("exa", "search")
    assert cost is not None
    assert "estimate" in note.lower()


def test_every_provider_mode_has_a_note() -> None:
    for provider, modes in PRICING.items():
        for mode, price in modes.items():
            assert price.note or price.per_1k_requests or price.input_per_1m, (
                f"{provider}/{mode} has neither a price nor an explanatory note"
            )


def test_table_renders_every_provider() -> None:
    rendered = table()
    for provider in PRICING:
        assert provider in rendered
