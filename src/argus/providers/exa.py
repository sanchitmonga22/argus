"""
Exa provider.

search        -> exa.search(type="auto"), fast ranked sources
deep_research -> exa.search(type="deep-reasoning"), Exa's slower
                 multi-query reasoning search — more thorough
                 ranking/retrieval, still returns ranked sources rather
                 than a synthesized narrative report.

Note: Exa's earlier standalone async Research agent (`exa.research.*`,
returning a synthesized markdown report) was retired — as of Aug 2026 it
returns HTTP 410 "RESEARCH_RETIRED" — so `deep_research` here uses the
`type="deep-reasoning"` search tier instead, which is Exa's documented
current replacement for multi-step reasoning search. `search_and_contents()`
is also deprecated in exa-py in favor of plain `search()` (which returns
text contents by default), so we use that too.

Exa's response includes an exact `cost_dollars.total` for the request —
we prefer that real, per-call figure over our static price-table estimate
whenever the SDK returns it.
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
            results = exa.search(
                query,
                type=search_type,
                num_results=num_results,
                contents={"text": {"maxCharacters": max_characters}},
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

            output = getattr(results, "output", None)
            answer = ""
            if output is not None:
                content = getattr(output, "content", "")
                answer = content if isinstance(content, str) else str(content)

            cost_dollars = getattr(results, "cost_dollars", None)
            usage = {"requests": 1}
            if cost_dollars is not None and getattr(cost_dollars, "total", None) is not None:
                cost_usd = cost_dollars.total
                cost_note = "exact cost reported by Exa's API for this request"
            else:
                cost_usd, cost_note = estimate_cost("exa", mode.value, usage)

            return ProviderResult(
                provider=self.name,
                mode=mode.value,
                query=query,
                answer=answer,
                sources=sources,
                usage=usage,
                elapsed_seconds=time.monotonic() - t0,
                cost_usd=cost_usd,
                cost_note=cost_note,
                model=f"search:{search_type}",
            )
        except Exception as exc:
            return ProviderResult(
                provider=self.name, mode=mode.value, query=query,
                elapsed_seconds=time.monotonic() - t0, error=str(exc),
            )
