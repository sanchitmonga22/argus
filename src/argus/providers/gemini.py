"""
Google Gemini provider, via the google-genai SDK's Interactions API.

search        -> client.interactions.create(tools=[{"type": "google_search"}])
deep_research -> client.interactions.create(agent="deep-research-preview-04-2026",
                 background=True), polled to completion

Note: citation extraction here follows Google's documented shape
(`content[i].annotations`, type "url_citation") but Google has not
published a verbatim runnable example for it as of Aug 2026 — this is
best-effort and defensively coded to degrade to "no sources" rather
than crash if the shape drifts.
"""

from __future__ import annotations

import time

from ..costs import estimate as estimate_cost
from .base import Mode, Provider, ProviderResult, Source

_POLL_INTERVAL, _POLL_TIMEOUT = 10.0, 1800.0


class GeminiProvider(Provider):
    name = "gemini"
    supported_modes = {Mode.SEARCH, Mode.DEEP_RESEARCH}
    env_key = "GEMINI_API_KEY"

    def _client(self):
        from google import genai

        return genai.Client(api_key=self.api_key)

    def run(self, query: str, mode: Mode, **kwargs) -> ProviderResult:
        if mode is Mode.SEARCH:
            return self._search(query, **kwargs)
        if mode is Mode.DEEP_RESEARCH:
            return self._deep_research(query, **kwargs)
        return self._unsupported(query, mode)

    def _search(self, query: str, *, model: str = "gemini-3.6-flash") -> ProviderResult:
        t0 = time.monotonic()
        try:
            client = self._client()
            interaction = client.interactions.create(
                model=model, input=query, tools=[{"type": "google_search"}],
            )
            answer = getattr(interaction, "output_text", "") or ""
            sources = _extract_sources(interaction)
            usage = {"requests": 1}
            cost, note = estimate_cost("gemini", "search", usage)

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
        agent: str = "deep-research-preview-04-2026",
        max_variant: bool = False,
    ) -> ProviderResult:
        t0 = time.monotonic()
        try:
            client = self._client()
            interaction = client.interactions.create(
                agent="deep-research-max-preview-04-2026" if max_variant else agent,
                input=query,
                agent_config={
                    "type": "deep-research",
                    "thinking_summaries": "auto",
                    "collaborative_planning": True,
                },
                background=True,
            )

            elapsed = 0.0
            while interaction.status == "in_progress" and elapsed < _POLL_TIMEOUT:
                time.sleep(_POLL_INTERVAL)
                elapsed += _POLL_INTERVAL
                interaction = client.interactions.get(interaction.id)

            if interaction.status != "completed":
                raise RuntimeError(f"Gemini deep research ended with status={interaction.status!r}")

            answer = getattr(interaction, "output_text", "") or ""
            sources = _extract_sources(interaction)
            usage = {"requests": 1}
            cost, note = estimate_cost("gemini", "deep_research", usage)

            return ProviderResult(
                provider=self.name, mode=Mode.DEEP_RESEARCH.value, query=query,
                answer=answer, sources=sources, usage=usage,
                elapsed_seconds=time.monotonic() - t0,
                cost_usd=cost, cost_note=note, model=agent,
            )
        except Exception as exc:
            return ProviderResult(
                provider=self.name, mode=Mode.DEEP_RESEARCH.value, query=query,
                elapsed_seconds=time.monotonic() - t0, error=str(exc),
            )


def _extract_sources(interaction) -> list[Source]:
    sources: list[Source] = []
    try:
        for step in getattr(interaction, "steps", None) or []:
            for block in getattr(step, "content", None) or []:
                for ann in getattr(block, "annotations", None) or []:
                    url = getattr(ann, "url", None)
                    if url:
                        sources.append(Source(title=getattr(ann, "title", "") or "", url=url))
    except Exception:
        pass
    return sources
