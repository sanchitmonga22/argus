"""
Opt-in live smoke tests — actually call each provider's API in `search`
mode with a trivial query and check we get a real, non-error response.

These are SKIPPED by default (and always skipped in CI) because they cost
money and require real API keys. Run them yourself after filling in
`.env`:

    pip install -e ".[all]"
    pytest tests/test_live_smoke.py -m live -v
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from argus.providers import REGISTRY, Mode

load_dotenv()

pytestmark = pytest.mark.live


def _has_key(env_key: str) -> bool:
    return bool(os.environ.get(env_key))


@pytest.mark.parametrize("provider_name", list(REGISTRY))
def test_provider_search_smoke(provider_name: str) -> None:
    cls = REGISTRY[provider_name]
    if not _has_key(cls.env_key):
        pytest.skip(f"{cls.env_key} not set — skipping live check for {provider_name}")

    provider = cls(api_key=os.environ[cls.env_key])
    result = provider.run("What year is it?", Mode.SEARCH)

    assert result.error is None, f"{provider_name} search failed: {result.error}"
    assert result.answer or result.sources, f"{provider_name} returned an empty result"
