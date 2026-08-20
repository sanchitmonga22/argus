"""
Unit tests for the pure response-parsing helpers in each provider module.
These never touch the network — they feed in lightweight stand-ins for
each SDK's response objects and check what gets extracted.
"""

from __future__ import annotations

from types import SimpleNamespace

from argus.providers.anthropic_provider import _dedupe
from argus.providers.anthropic_provider import _extract_sources as anthropic_sources
from argus.providers.base import Source
from argus.providers.gemini import _extract_sources as gemini_sources
from argus.providers.gemini import _usage_dict as gemini_usage_dict
from argus.providers.openai_provider import _extract_annotations, _usage_dict
from argus.providers.perplexity import _parse_agent_output


def test_openai_extract_annotations() -> None:
    ann = SimpleNamespace(type="url_citation", url="https://a.com", title="A")
    block = SimpleNamespace(annotations=[ann])
    item = SimpleNamespace(content=[block])
    response = SimpleNamespace(output=[item])

    sources = _extract_annotations(response)

    assert sources == [Source(title="A", url="https://a.com")]


def test_openai_extract_annotations_degrades_gracefully_on_bad_shape() -> None:
    assert _extract_annotations(SimpleNamespace(output=None)) == []
    assert _extract_annotations(SimpleNamespace()) == []


def test_openai_usage_dict() -> None:
    response = SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=20), output=[])
    assert _usage_dict(response) == {"requests": 1, "searches": 0, "input_tokens": 10, "output_tokens": 20}


def test_openai_usage_dict_missing_usage() -> None:
    assert _usage_dict(SimpleNamespace(usage=None, output=[])) == {"requests": 1, "searches": 0}


def test_openai_usage_dict_counts_web_search_calls() -> None:
    response = SimpleNamespace(
        usage=None,
        output=[SimpleNamespace(type="web_search_call"), SimpleNamespace(type="message"), SimpleNamespace(type="web_search_call")],
    )
    assert _usage_dict(response)["searches"] == 2


def test_gemini_extract_sources() -> None:
    ann = SimpleNamespace(url="https://g.com", title="G")
    block = SimpleNamespace(annotations=[ann])
    step = SimpleNamespace(content=[block])
    interaction = SimpleNamespace(steps=[step])

    sources = gemini_sources(interaction)

    assert sources == [Source(title="G", url="https://g.com")]


def test_gemini_extract_sources_missing_steps() -> None:
    assert gemini_sources(SimpleNamespace()) == []


def test_gemini_usage_dict_extracts_tokens_and_search_count() -> None:
    usage = SimpleNamespace(
        total_input_tokens=42,
        total_output_tokens=99,
        grounding_tool_count=[
            SimpleNamespace(type="google_search", count=3),
            SimpleNamespace(type="google_maps", count=1),  # a different tool — must not be counted
        ],
    )
    result = gemini_usage_dict(SimpleNamespace(usage=usage))
    assert result == {"requests": 1, "searches": 3, "input_tokens": 42, "output_tokens": 99}


def test_gemini_usage_dict_missing_usage() -> None:
    assert gemini_usage_dict(SimpleNamespace(usage=None)) == {"requests": 1, "searches": 0}


def test_anthropic_extract_sources_web_search_result() -> None:
    result_item = SimpleNamespace(title="R", url="https://r.com", page_age="2026-01-01")
    block = SimpleNamespace(type="web_search_tool_result", content=[result_item])
    response = SimpleNamespace(content=[block])

    sources = anthropic_sources(response)

    assert sources == [Source(title="R", url="https://r.com", published_date="2026-01-01")]


def test_anthropic_extract_sources_text_citations() -> None:
    citation = SimpleNamespace(url="https://c.com", title="C")
    block = SimpleNamespace(type="text", citations=[citation])
    response = SimpleNamespace(content=[block])

    sources = anthropic_sources(response)

    assert sources == [Source(title="C", url="https://c.com")]


def test_anthropic_dedupe_preserves_order_and_drops_repeats() -> None:
    sources = [Source(title="1", url="https://x.com"), Source(title="2", url="https://x.com"), Source(title="3", url="https://y.com")]
    deduped = _dedupe(sources)
    assert [s.url for s in deduped] == ["https://x.com", "https://y.com"]


def test_perplexity_parse_agent_output_text_and_annotations() -> None:
    data = {
        "output": [
            {"content": [{"type": "text", "text": "hello", "annotations": [{"url": "https://p.com", "title": "P"}]}]}
        ]
    }
    answer, sources = _parse_agent_output(data)
    assert answer == "hello"
    assert sources == [Source(title="P", url="https://p.com")]


def test_perplexity_parse_agent_output_falls_back_to_output_text() -> None:
    answer, sources = _parse_agent_output({"output_text": "fallback answer"})
    assert answer == "fallback answer"
    assert sources == []


def test_perplexity_parse_agent_output_handles_empty_dict() -> None:
    answer, sources = _parse_agent_output({})
    assert answer == ""
    assert sources == []
