"""
Perplexity provider, built on the Agent API — the successor to the
Sonar chat-completions surface, which Perplexity is retiring on
2026-09-27 (see docs.perplexity.ai/docs/agent-api/migrate-from-sonar).

search        -> sync Agent API call, tools=[web_search], preset="low"
deep_research -> Agent API call with preset="xhigh" (the most agentic,
                 highest-quality tier — successor to sonar-deep-research /
                 the old "ultra" preset), background=True, polled to completion

Valid presets as of Aug 2026 (docs.perplexity.ai/docs/agent-api/presets),
low to high cost/quality: fast, low, medium, high, xhigh, wide-research.
"""

from __future__ import annotations

import time

import httpx

from ..costs import estimate as estimate_cost
from .base import Mode, Provider, ProviderResult, Source

_BASE = "https://api.perplexity.ai"
_POLL_INITIAL, _POLL_FACTOR, _POLL_MAX, _POLL_TIMEOUT = 5.0, 1.5, 20.0, 900.0


class PerplexityProvider(Provider):
    name = "perplexity"
    supported_modes = {Mode.SEARCH, Mode.DEEP_RESEARCH}
    env_key = "PERPLEXITY_API_KEY"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def run(self, query: str, mode: Mode, **kwargs) -> ProviderResult:
        if mode is Mode.SEARCH:
            return self._agent_call(query, mode, preset=kwargs.pop("preset", "low"), background=False, **kwargs)
        if mode is Mode.DEEP_RESEARCH:
            return self._agent_call(query, mode, preset=kwargs.pop("preset", "xhigh"), background=True, **kwargs)
        return self._unsupported(query, mode)

    def _agent_call(
        self,
        query: str,
        mode: Mode,
        *,
        preset: str,
        background: bool,
        model: str = "openai/gpt-5.6-sol",
        system_prompt: str | None = None,
    ) -> ProviderResult:
        t0 = time.monotonic()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        payload = {
            "model": model,
            "input": query,
            "tools": [{"type": "web_search"}],
            "preset": preset,
            "background": background,
        }

        try:
            with httpx.Client(timeout=httpx.Timeout(connect=15.0, read=60.0, write=30.0, pool=10.0)) as client:
                resp = client.post(f"{_BASE}/v1/agent", headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()

                if background:
                    job_id = data["id"]
                    data = self._poll(client, job_id)

            answer, sources = _parse_agent_output(data)
            usage = data.get("usage", {}) or {}
            cost_usage = {
                "requests": 1,
                "input_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
                "output_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
            }
            cost, note = estimate_cost("perplexity", mode.value, cost_usage)

            return ProviderResult(
                provider=self.name,
                mode=mode.value,
                query=query,
                answer=answer,
                sources=sources,
                usage=cost_usage,
                elapsed_seconds=time.monotonic() - t0,
                cost_usd=cost,
                cost_note=note,
                model=f"{model} (preset={preset})",
                raw={"id": data.get("id")},
            )
        except Exception as exc:
            return ProviderResult(
                provider=self.name, mode=mode.value, query=query,
                elapsed_seconds=time.monotonic() - t0, error=str(exc),
            )

    def _poll(self, client: httpx.Client, job_id: str) -> dict:
        interval, elapsed = _POLL_INITIAL, 0.0
        while elapsed < _POLL_TIMEOUT:
            time.sleep(interval)
            elapsed += interval
            resp = client.get(f"{_BASE}/v1/agent/{job_id}", headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "completed":
                return data
            if status in ("failed", "cancelled"):
                raise RuntimeError(f"Perplexity agent job {status}: {data.get('error')}")
            interval = min(interval * _POLL_FACTOR, _POLL_MAX)
        raise TimeoutError(f"Perplexity agent job {job_id} timed out after {_POLL_TIMEOUT:.0f}s")


def _parse_agent_output(data: dict) -> tuple[str, list[Source]]:
    """Agent API responses are shaped like OpenAI's Responses API:
    output -> [ { content: [ { type: 'text'|..., text, annotations } ] } ]
    Defensive: field names for this newer endpoint aren't all pinned down
    in the docs yet, so we fall back gracefully rather than raising.
    """
    answer_parts: list[str] = []
    sources: list[Source] = []

    for item in data.get("output", []) or []:
        for block in item.get("content", []) or []:
            if block.get("type") == "text" or "text" in block:
                answer_parts.append(block.get("text", ""))
            for ann in block.get("annotations", []) or []:
                url = ann.get("url")
                if url:
                    sources.append(Source(title=ann.get("title", ""), url=url))

    if not answer_parts and "output_text" in data:
        answer_parts.append(data["output_text"])

    for c in data.get("citations", []) or []:
        if isinstance(c, str):
            sources.append(Source(title="", url=c))

    return "\n".join(p for p in answer_parts if p), sources
