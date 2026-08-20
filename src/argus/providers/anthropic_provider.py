"""
Anthropic (Claude) provider, via the Messages API's server-executed
web_search / web_fetch tools. Anthropic has no dedicated deep-research
endpoint (see docs.claude.com/.../web-search-tool), so:

search        -> one messages.create call, web_search only, max_uses=3
deep_research -> web_search + web_fetch together, higher max_uses, and we
                 keep resending on stop_reason="pause_turn" (Anthropic's
                 documented way to let a long multi-search turn continue)
                 until the model reaches "end_turn" or a hard turn cap.
"""

from __future__ import annotations

import time

from ..costs import estimate as estimate_cost
from .base import Mode, Provider, ProviderResult, Source

_MAX_CONTINUATIONS = 6


class AnthropicProvider(Provider):
    name = "anthropic"
    supported_modes = {Mode.SEARCH, Mode.DEEP_RESEARCH}
    env_key = "ANTHROPIC_API_KEY"

    def _client(self):
        import anthropic

        return anthropic.Anthropic(api_key=self.api_key)

    def run(self, query: str, mode: Mode, **kwargs) -> ProviderResult:
        if mode is Mode.SEARCH:
            return self._run(query, mode, tools=[_web_search(max_uses=3)], max_turns=1, **kwargs)
        if mode is Mode.DEEP_RESEARCH:
            return self._run(
                query, mode,
                tools=[_web_search(max_uses=10), _web_fetch(max_uses=10)],
                max_turns=_MAX_CONTINUATIONS,
                **kwargs,
            )
        return self._unsupported(query, mode)

    def _run(
        self,
        query: str,
        mode: Mode,
        *,
        tools: list[dict],
        max_turns: int,
        model: str = "claude-sonnet-5",
        max_tokens: int = 4096,
    ) -> ProviderResult:
        t0 = time.monotonic()
        try:
            client = self._client()
            messages = [{"role": "user", "content": query}]
            sources: list[Source] = []
            total_input = total_output = 0
            search_calls = 0
            response = None

            for _ in range(max_turns):
                response = client.messages.create(
                    model=model, max_tokens=max_tokens, messages=messages, tools=tools,
                )
                usage = getattr(response, "usage", None)
                if usage:
                    total_input += getattr(usage, "input_tokens", 0) or 0
                    total_output += getattr(usage, "output_tokens", 0) or 0
                    server_tool_use = getattr(usage, "server_tool_use", None)
                    if server_tool_use:
                        search_calls += getattr(server_tool_use, "web_search_requests", 0) or 0

                sources.extend(_extract_sources(response))

                if response.stop_reason != "pause_turn":
                    break
                messages.append({"role": "assistant", "content": response.content})

            answer = "\n".join(
                block.text for block in (response.content if response else []) if getattr(block, "type", None) == "text"
            )
            usage_dict = {
                "requests": 1,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "searches": search_calls or 1,
            }
            cost, note = estimate_cost("anthropic", mode.value, usage_dict)

            return ProviderResult(
                provider=self.name, mode=mode.value, query=query,
                answer=answer, sources=_dedupe(sources), usage=usage_dict,
                elapsed_seconds=time.monotonic() - t0,
                cost_usd=cost, cost_note=note, model=model,
            )
        except Exception as exc:
            return ProviderResult(
                provider=self.name, mode=mode.value, query=query,
                elapsed_seconds=time.monotonic() - t0, error=str(exc),
            )


def _web_search(max_uses: int) -> dict:
    return {"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}


def _web_fetch(max_uses: int) -> dict:
    return {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": max_uses}


def _extract_sources(response) -> list[Source]:
    sources: list[Source] = []
    for block in getattr(response, "content", None) or []:
        btype = getattr(block, "type", None)
        if btype == "web_search_tool_result":
            content = getattr(block, "content", None)
            if isinstance(content, list):
                for r in content:
                    sources.append(Source(
                        title=getattr(r, "title", "") or "",
                        url=getattr(r, "url", ""),
                        published_date=getattr(r, "page_age", None),
                    ))
        elif btype == "web_fetch_tool_result":
            result = getattr(block, "content", None)
            url = getattr(result, "url", None)
            if url:
                sources.append(Source(title="", url=url, published_date=getattr(result, "retrieved_at", None)))
        elif btype == "text":
            for c in getattr(block, "citations", None) or []:
                url = getattr(c, "url", None)
                if url:
                    sources.append(Source(title=getattr(c, "title", "") or "", url=url))
    return sources


def _dedupe(sources: list[Source]) -> list[Source]:
    seen: set[str] = set()
    out = []
    for s in sources:
        if s.url and s.url not in seen:
            seen.add(s.url)
            out.append(s)
    return out
