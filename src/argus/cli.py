"""Command-line interface: `argus run|providers|costs`."""

from __future__ import annotations

import argparse
import json
import sys

from . import costs as costs_module
from .core import Argus
from .providers import REGISTRY


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="argus", description="One query, every search engine, in parallel.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run a query against one or more providers")
    run_p.add_argument("query", nargs="+", help="The research query")
    run_p.add_argument(
        "--mode", choices=["search", "deep_research"], default="search",
        help="search = fast grounded answer; deep_research = slower multi-step report (default: search)",
    )
    run_p.add_argument(
        "--providers", default=None,
        help=f"Comma-separated subset of {','.join(REGISTRY)} (default: all configured providers)",
    )
    run_p.add_argument("--output-dir", default=None, help="Override the output folder for this run")
    run_p.add_argument("--no-save", action="store_true", help="Don't write report.md/results.json/metadata.json")
    run_p.add_argument("--json", action="store_true", help="Print the raw result as JSON instead of the markdown report")
    run_p.add_argument("--dry-run", action="store_true", help="Only print the estimated cost, make no API calls")
    run_p.add_argument("--yes", "-y", action="store_true", help="Skip the pre-flight cost confirmation prompt")

    sub.add_parser("providers", help="List providers and whether each is configured")

    costs_p = sub.add_parser("costs", help="Show the pricing table, or an estimate for your configured providers")
    costs_p.add_argument("--mode", choices=["search", "deep_research"], default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "providers":
        return _cmd_providers()
    if args.command == "costs":
        return _cmd_costs(args.mode)
    if args.command == "run":
        return _cmd_run(args)

    parser.print_help()
    return 1


def _cmd_providers() -> int:
    agent = Argus()
    configured = set(agent.available_providers())
    for name, cls in REGISTRY.items():
        status = "configured" if name in configured else f"missing {cls.env_key}"
        modes = ", ".join(m.value for m in cls.supported_modes)
        print(f"  {name:<12} [{status:<22}] modes: {modes}")
    return 0


def _cmd_costs(mode: str | None) -> int:
    if mode is None:
        print(costs_module.table())
        return 0

    agent = Argus()
    estimates = agent.preflight_cost(mode=mode)
    if not estimates:
        print("No providers configured. Set at least one provider's API key first (see `argus providers`).")
        return 1

    print(f"Pre-flight cost estimate for mode={mode!r} (rough, based on typical usage):\n")
    total = 0.0
    for provider, (cost, note) in estimates.items():
        if cost is None:
            print(f"  {provider:<12} unknown — {note}")
        else:
            total += cost
            print(f"  {provider:<12} ~${cost:.4f}  ({note})")
    print(f"\n  {'TOTAL':<12} ~${total:.4f}  (sum of providers with a known estimate)")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    query = " ".join(args.query)
    providers = args.providers.split(",") if args.providers else None

    agent = Argus()

    estimates = agent.preflight_cost(mode=args.mode, providers=providers)
    if estimates:
        print("Estimated cost before running:", file=sys.stderr)
        for provider, (cost, note) in estimates.items():
            label = f"~${cost:.4f}" if cost is not None else "unknown"
            print(f"  {provider:<12} {label}  ({note})", file=sys.stderr)
        print(file=sys.stderr)

    if args.dry_run:
        return 0

    if not args.yes and sys.stdin.isatty():
        confirm = input("Proceed? [Y/n] ").strip().lower()
        if confirm and confirm != "y":
            print("Aborted.")
            return 1

    result = agent.research(
        query, mode=args.mode, providers=providers,
        save=not args.no_save, output_dir=args.output_dir,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print(result.to_markdown())

    return 0 if not result.failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
