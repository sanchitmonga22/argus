from __future__ import annotations

import pytest

from argus.providers.base import Mode, Provider, ProviderResult, Source


class FakeProvider(Provider):
    """A provider double that never touches the network."""

    name = "fake"
    supported_modes = {Mode.SEARCH, Mode.DEEP_RESEARCH}
    env_key = "FAKE_API_KEY"

    def run(self, query: str, mode: Mode, **kwargs) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            mode=mode.value,
            query=query,
            answer=f"fake answer for {query!r}",
            sources=[Source(title="Example", url="https://example.com")],
            usage={"requests": 1, "input_tokens": 100, "output_tokens": 100},
            elapsed_seconds=0.01,
            cost_usd=0.01,
            model="fake-model",
        )


class FailingFakeProvider(Provider):
    name = "broken"
    supported_modes = {Mode.SEARCH}
    env_key = "BROKEN_API_KEY"

    def run(self, query: str, mode: Mode, **kwargs) -> ProviderResult:
        return ProviderResult(provider=self.name, mode=mode.value, query=query, error="boom")


@pytest.fixture
def fake_registry():
    return {"fake": FakeProvider, "broken": FailingFakeProvider}
