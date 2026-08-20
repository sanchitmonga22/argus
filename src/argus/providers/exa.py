"""
Exa provider.

search        -> exa.search_and_contents(type="auto"), fast ranked sources
deep_research -> exa.search_and_contents(type="deep-reasoning"), Exa's
                 slower multi-query reasoning search — more thorough
                 ranking/retrieval, still returns ranked sources rather
                 than a synthesized narrative report.

Note: Exa's earlier standalone async Research agent (`exa.research.*`,
returning a synthesized markdown report) was retired — as of Aug 2026 it
returns HTTP 410 "RESEARCH_RETIRED" — so `deep_research` here uses the
`type="deep-reasoning"` search tier instead, which is Exa's documented
current replacement for multi-step reasoning search.
"""

from __future__ import annotations

import time

from ..costs import estimate as estimate_cost
from .base import Mode, Provider, ProviderResult, Source


class ExaProvider(Provider):
    name = "exa"
    supported_modes = {Mode.SEARCH, Mode.DEEP_RESEARCH}
    env_key = "EXA_API_KEY"

    def _client(self):
        from exa_py import Exa

        return Exa(api_key=self.api_key)

    def run(self, query: str, mode: Mode, **kwargs) -> ProviderResult:
        if mode is Mode.SEARCH:
            return self._run_search(query, mode, search_type=kwargs.pop("search_type", "auto"), **kwargs)
        if mode is Mode.DEEP_RESEARCH:
            kwargs.setdefault("num_results", 20)
            return self._run_search(query, mode, search_type="deep-reasoning", **kwargs)
        return self._unsupported(query, mode)

    def _run_search(
        self,
        query: str,
        mode: Mode,
        *,
        search_type: str,
        num_results: int = 10,
        max_characters: int = 20_000,
    ) -> ProviderResult:
        t0 = time.monotonic()
        try:
            exa = self._client()
            results = exa.search_and_contents(
                query,
                type=search_type,
                num_results=num_results,
                text={"max_characters": max_characters},
            )
            sources = [
                Source(
                    title=r.title or "",
                    url=r.url,
                    snippet=(r.text or "")[:500],
                    published_date=getattr(r, "published_date", None),
                )
                for r in results.results
            ]
            answer = getattr(results, "output", "") or ""
            usage = {"requests": 1}
            cost, note = estimate_cost("exa", mode.value, usage)

            return ProviderResult(
                provider=self.name,
                mode=mode.value,
                query=query,
                answer=answer,
                sources=sources,
                usage=usage,
                elapsed_seconds=time.monotonic() - t0,
                cost_usd=cost,
                cost_note=note,
                model=f"search:{search_type}",
            )
        except Exception as exc:
            return ProviderResult(
                provider=self.name, mode=mode.value, query=query,
                elapsed_seconds=time.monotonic() - t0, error=str(exc),
            )
