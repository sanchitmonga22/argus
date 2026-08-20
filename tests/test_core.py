from __future__ import annotations

import json

import pytest

from argus.core import Argus, _run_folder


def test_no_providers_configured_raises(monkeypatch, fake_registry) -> None:
    monkeypatch.setattr("argus.core.REGISTRY", fake_registry)
    agent = Argus(load_env=False)
    with pytest.raises(ValueError, match="No providers configured"):
        agent.research("test query")


def test_research_runs_configured_fake_provider(monkeypatch, fake_registry, tmp_path) -> None:
    monkeypatch.setattr("argus.core.REGISTRY", fake_registry)
    agent = Argus(api_keys={"fake": "test-key"}, outputs_dir=tmp_path, load_env=False)

    result = agent.research("what is argus?", mode="search")

    assert len(result.succeeded) == 1
    assert result.succeeded[0].provider == "fake"
    assert result.total_cost_usd == 0.01
    assert not result.failed


def test_unconfigured_and_unknown_providers_are_reported_as_errors(monkeypatch, fake_registry, tmp_path) -> None:
    monkeypatch.setattr("argus.core.REGISTRY", fake_registry)
    agent = Argus(api_keys={"fake": "test-key"}, outputs_dir=tmp_path, load_env=False)

    result = agent.research("q", providers=["fake", "broken", "nonexistent"])

    by_provider = {r.provider: r for r in result.results}
    assert by_provider["fake"].error is None
    assert "not configured" in by_provider["broken"].error
    assert "unknown provider" in by_provider["nonexistent"].error


def test_save_writes_all_three_files(monkeypatch, fake_registry, tmp_path) -> None:
    monkeypatch.setattr("argus.core.REGISTRY", fake_registry)
    agent = Argus(api_keys={"fake": "test-key"}, outputs_dir=tmp_path, load_env=False)

    out_dir = tmp_path / "one_run"
    agent.research("q", output_dir=out_dir)

    assert (out_dir / "report.md").exists()
    assert (out_dir / "results.json").exists()
    assert (out_dir / "metadata.json").exists()

    data = json.loads((out_dir / "results.json").read_text())
    assert data["query"] == "q"
    assert data["results"][0]["provider"] == "fake"


def test_to_markdown_includes_query_cost_and_sources(monkeypatch, fake_registry, tmp_path) -> None:
    monkeypatch.setattr("argus.core.REGISTRY", fake_registry)
    agent = Argus(api_keys={"fake": "test-key"}, outputs_dir=tmp_path, load_env=False)

    result = agent.research("hello world", save=False)
    md = result.to_markdown()

    assert "hello world" in md
    assert "fake" in md
    assert "example.com" in md
    assert "$0.01" in md


def test_run_folder_slugifies_query() -> None:
    folder = _run_folder("What is the Qualcomm Hexagon HMX?!", "2026-08-20T10:00:00Z")
    assert folder.startswith("20260820_100000_")
    assert "qualcomm_hexagon_hmx" in folder
    assert "?" not in folder
