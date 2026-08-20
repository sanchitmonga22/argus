"""Argus — one query, every search engine, in parallel."""

from __future__ import annotations

from .core import Argus, ArgusResult
from .costs import estimate as estimate_cost
from .costs import preflight_estimate
from .providers import REGISTRY as PROVIDERS
from .providers import Mode, Provider, ProviderResult, Source

__version__ = "0.1.0"

__all__ = [
    "Argus",
    "ArgusResult",
    "Mode",
    "Provider",
    "ProviderResult",
    "Source",
    "PROVIDERS",
    "estimate_cost",
    "preflight_estimate",
    "__version__",
]
