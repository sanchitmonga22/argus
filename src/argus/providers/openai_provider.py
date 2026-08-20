"""
OpenAI provider, via the Responses API.

search        -> client.responses.create(tools=[{"type": "web_search"}])
deep_research -> o3-deep-research (or o4-mini-deep-research), background=True,
                 polled to completion
"""

from __future__ import annotations

import time

from ..costs import estimate as estimate_cost
from .base import Mode, Provider, ProviderResult, Source

_POLL_INTERVAL, _POLL_TIMEOUT = 5.0, 1800.0


class OpenAIProvider(Provider):
    name = "openai"
    supported_modes = {Mode.SEARCH, Mode.DEEP_RESEARCH}
    env_key = "OPENAI_API_KEY"

    def _client(self):
        from openai import OpenAI

        return OpenAI(api_key=self.api_key)

    def run(self, query: str, mode: Mode, **kwargs) -> ProviderResult:
        if mode is Mode.SEARCH:
            return self._search(query, **kwargs)
        if mode is Mode.DEEP_RESEARCH:
            return self._deep_research(query, **kwargs)
        return self._unsupported(query, mode)

    def _search(
        self,
        query: str,
        *,
        model: str = "gpt-5.6-sol",
        search_context_size: str = "medium",
        allowed_domains: list[str] | None = None,
    ) -> ProviderResult:
        t0 = time.monotonic()
        try:
            client = self._client()
            tool: dict = {"type": "web_search", "search_context_size": search_context_size}
            if allowed_domains:
                tool["filters"] = {"allowed_domains": allowed_domains}

            response = client.responses.create(model=model, tools=[tool], input=query)

            answer = getattr(response, "output_text", "") or ""
            sources = _extract_annotations(response)
            usage = _usage_dict(response)
            cost, note = estimate_cost("openai", "search", usage)

            return ProviderResult(
                provider=self.name, mode=Mode.SEARCH.value, query=query,
                answer=answer, sources=sources, usage=usage,
                elapsed_seconds=time.monotonic() - t0,
                cost_usd=cost, cost_note=note, model=model,
            )
        except Exception as exc:
            return ProviderResult(
                provider=self.name, mode=Mode.SEARCH.value, query=query,
                elapsed_seconds=time.monotonic() - t0, error=str(exc),
            )

    def _deep_research(
        self,
        query: str,
        *,
        model: str = "o3-deep-research",
        system_prompt: str = (
            "You are a deep research assistant. Produce a comprehensive, "
            "well-cited report answering the user's question."
        ),
        max_tool_calls: int | None = None,
    ) -> ProviderResult:
        t0 = time.monotonic()
        try:
            client = self._client()
            kwargs = dict(
                model=model,
                input=[
                    {"role": "developer", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": query}]},
                ],
                reasoning={"summary": "auto"},
                background=True,
                tools=[{"type": "web_search"}],
            )
            if max_tool_calls:
                kwargs["max_tool_calls"] = max_tool_calls

            response = client.responses.create(**kwargs)

            elapsed = 0.0
            while response.status in ("queued", "in_progress") and elapsed < _POLL_TIMEOUT:
                time.sleep(_POLL_INTERVAL)
                elapsed += _POLL_INTERVAL
                response = client.responses.retrieve(response.id)

            if response.status not in ("completed",):
                raise RuntimeError(f"OpenAI deep research ended with status={response.status!r}")

            answer = getattr(response, "output_text", "") or ""
            sources = _extract_annotations(response)
            usage = _usage_dict(response)
            cost, note = estimate_cost("openai", "deep_research", usage)

            return ProviderResult(
                provider=self.name, mode=Mode.DEEP_RESEARCH.value, query=query,
                answer=answer, sources=sources, usage=usage,
                elapsed_seconds=time.monotonic() - t0,
                cost_usd=cost, cost_note=note, model=model,
            )
        except Exception as exc:
            return ProviderResult(
                provider=self.name, mode=Mode.DEEP_RESEARCH.value, query=query,
                elapsed_seconds=time.monotonic() - t0, error=str(exc),
            )


def _extract_annotations(response) -> list[Source]:
    sources: list[Source] = []
    try:
        for item in response.output:
            content = getattr(item, "content", None) or []
            for block in content:
                for ann in getattr(block, "annotations", None) or []:
                    if getattr(ann, "type", None) == "url_citation" or hasattr(ann, "url"):
                        sources.append(Source(title=getattr(ann, "title", "") or "", url=ann.url))
    except Exception:
        pass
    return sources


def _usage_dict(response) -> dict:
    usage = getattr(response, "usage", None)
    result = {"requests": 1, "searches": _count_web_searches(response)}
    if usage is not None:
        result["input_tokens"] = getattr(usage, "input_tokens", 0) or 0
        result["output_tokens"] = getattr(usage, "output_tokens", 0) or 0
    return result


def _count_web_searches(response) -> int:
    """Count actual `web_search_call` items in the output — OpenAI's $10/1k
    fee is per search invocation, not per API request, and a single call
    can trigger zero, one, or several searches."""
    try:
        return sum(1 for item in response.output if getattr(item, "type", None) == "web_search_call")
    except Exception:
        return 0
