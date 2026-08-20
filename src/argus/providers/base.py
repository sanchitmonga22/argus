"""Common types shared by every provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Mode(str, Enum):
    """Every provider speaks one of these two modes."""

    SEARCH = "search"
    DEEP_RESEARCH = "deep_research"


@dataclass
class Source:
    title: str
    url: str
    snippet: str = ""
    published_date: str | None = None


@dataclass
class ProviderResult:
    provider: str
    mode: str
    query: str
    answer: str = ""
    sources: list[Source] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    cost_usd: float | None = None
    cost_note: str | None = None
    model: str | None = None
    error: str | None = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "query": self.query,
            "answer": self.answer,
            "sources": [s.__dict__ for s in self.sources],
            "usage": self.usage,
            "elapsed_seconds": self.elapsed_seconds,
            "cost_usd": self.cost_usd,
            "cost_note": self.cost_note,
            "model": self.model,
            "error": self.error,
        }


class Provider:
    """Base class every provider implements.

    Subclasses only need to fill in `name`, `supported_modes`, and `run`.
    `run` must never raise — errors are caught by the orchestrator, but
    providers should still prefer returning a `ProviderResult(error=...)`
    so partial failures are recorded per-provider rather than aborting.
    """

    name: str = "base"
    supported_modes: set[Mode] = {Mode.SEARCH}
    env_key: str = ""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    def run(self, query: str, mode: Mode, **kwargs) -> ProviderResult:
        raise NotImplementedError

    def _unsupported(self, query: str, mode: Mode) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            mode=mode.value,
            query=query,
            error=f"{self.name} does not support mode={mode.value!r} "
            f"(supported: {sorted(m.value for m in self.supported_modes)})",
        )
