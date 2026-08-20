"""
Argus — the orchestrator. Fans a single query out to every configured
provider in parallel, in either `search` or `deep_research` mode, and
combines the individual results into one report + one JSON dump.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import load_file_env
from .costs import preflight_estimate
from .providers import REGISTRY, Mode, ProviderResult

DEFAULT_OUTPUTS_DIR = Path.cwd() / "outputs"


@dataclass
class ArgusResult:
    query: str
    run_id: str
    mode: str
    started_at: str
    finished_at: str = ""
    results: list[ProviderResult] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float | None:
        known = [r.cost_usd for r in self.results if r.cost_usd is not None]
        return round(sum(known), 6) if known else None

    @property
    def succeeded(self) -> list[ProviderResult]:
        return [r for r in self.results if r.error is None]

    @property
    def failed(self) -> list[ProviderResult]:
        return [r for r in self.results if r.error is not None]

    def to_markdown(self) -> str:
        lines = [
            "# Argus Research Report", "",
            f"**Query:** {self.query}",
            f"**Mode:** {self.mode}",
            f"**Run ID:** `{self.run_id}`",
            f"**Generated:** {self.finished_at}",
        ]
        if self.total_cost_usd is not None:
            lines.append(f"**Estimated cost:** ${self.total_cost_usd:.4f}")
        lines.append("")

        if self.failed:
            lines += ["## ⚠ Providers that failed", ""]
            for r in self.failed:
                lines.append(f"- **{r.provider}**: {r.error}")
            lines.append("")

        for r in self.succeeded:
            cost_str = f"${r.cost_usd:.4f}" if r.cost_usd is not None else (r.cost_note or "n/a")
            lines += [
                "---", "",
                f"## {r.provider} ({r.mode})",
                f"*Model: `{r.model or 'n/a'}` · {r.elapsed_seconds:.1f}s · cost: {cost_str}*",
                "",
            ]
            if r.answer:
                lines += [r.answer, ""]
            if r.sources:
                lines += [f"### Sources ({len(r.sources)})", ""]
                for i, s in enumerate(r.sources, 1):
                    line = f"{i}. [{s.title or s.url}]({s.url})"
                    if s.published_date:
                        line += f" — {s.published_date}"
                    lines.append(line)
                lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "mode": self.mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_cost_usd": self.total_cost_usd,
            "results": [r.to_dict() for r in self.results],
        }

    def save(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "report.md").write_text(self.to_markdown(), encoding="utf-8")
        (output_dir / "results.json").write_text(
            json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8"
        )
        meta = {
            "run_id": self.run_id, "query": self.query, "mode": self.mode,
            "started_at": self.started_at, "finished_at": self.finished_at,
            "providers": [r.provider for r in self.results],
            "succeeded": [r.provider for r in self.succeeded],
            "failed": {r.provider: r.error for r in self.failed},
            "total_cost_usd": self.total_cost_usd,
        }
        (output_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


class Argus:
    """
    agent = Argus()
    result = agent.research("your query", mode="search")
    result = agent.research("your query", mode="deep_research", providers=["exa", "anthropic"])
    """

    def __init__(
        self,
        api_keys: dict[str, str] | None = None,
        outputs_dir: Path | None = None,
        load_env: bool = True,
    ) -> None:
        # Priority: explicit api_keys > real env vars > ./.env (project) >
        # ~/.config/argus/.env (global, written by `argus init`).
        file_env = load_file_env() if load_env else {}

        api_keys = api_keys or {}
        self._instances = {}
        for name, cls in REGISTRY.items():
            key = api_keys.get(name) or os.environ.get(cls.env_key) or file_env.get(cls.env_key, "")
            if key:
                self._instances[name] = cls(api_key=key)

        self.outputs_dir = Path(outputs_dir) if outputs_dir else DEFAULT_OUTPUTS_DIR

    def available_providers(self) -> list[str]:
        return sorted(self._instances)

    def preflight_cost(self, mode: str = "search", providers: list[str] | None = None) -> dict[str, tuple]:
        """Rough per-provider cost estimate, computed before any API call."""
        chosen = providers or self.available_providers()
        return {p: preflight_estimate(p, mode) for p in chosen}

    def research(
        self,
        query: str,
        *,
        mode: str = "search",
        providers: list[str] | None = None,
        provider_kwargs: dict[str, dict] | None = None,
        save: bool = True,
        output_dir: Path | None = None,
    ) -> ArgusResult:
        mode_enum = Mode(mode)
        provider_kwargs = provider_kwargs or {}
        chosen = providers or self.available_providers()
        if not chosen:
            raise ValueError(
                "No providers configured. Set at least one of: "
                + ", ".join(cls.env_key for cls in REGISTRY.values())
            )

        run_id = str(uuid.uuid4())[:8]
        started_at = _now_iso()
        results: list[ProviderResult] = []

        runnable = [p for p in chosen if p in self._instances]
        unconfigured = [p for p in chosen if p not in self._instances]
        for p in unconfigured:
            results.append(ProviderResult(
                provider=p, mode=mode, query=query,
                error=f"{p} not configured — set {REGISTRY[p].env_key}" if p in REGISTRY else f"unknown provider {p!r}",
            ))

        with ThreadPoolExecutor(max_workers=max(len(runnable), 1)) as pool:
            futures = {
                pool.submit(self._instances[p].run, query, mode_enum, **provider_kwargs.get(p, {})): p
                for p in runnable
            }
            for future in as_completed(futures):
                results.append(future.result())

        result = ArgusResult(
            query=query, run_id=run_id, mode=mode,
            started_at=started_at, finished_at=_now_iso(), results=results,
        )

        if save:
            target = Path(output_dir) if output_dir else self.outputs_dir / _run_folder(query, started_at)
            result.save(target)

        return result


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_folder(query: str, ts: str) -> str:
    date_part = ts.replace("-", "").replace("T", "_").replace(":", "").replace("Z", "")[:15]
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower())[:50].strip("_")
    return f"{date_part}_{slug}"
