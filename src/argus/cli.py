"""Command-line interface: `argus init|run|providers|costs`."""

from __future__ import annotations

import argparse
import json
import os
import sys
from getpass import getpass

from . import costs as costs_module
from .config import config_env_path, load_file_env, mask, save_keys
from .core import Argus
from .providers import REGISTRY

# Where to get a key for each provider, shown during `argus init`.
_KEY_URLS = {
    "exa": "https://dashboard.exa.ai/api-keys",
    "perplexity": "https://console.perplexity.ai",
    "openai": "https://platform.openai.com/account/api-keys",
    "gemini": "https://aistudio.google.com/apikey",
    "anthropic": "https://console.anthropic.com/settings/keys",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="argus", description="One query, every search engine, in parallel.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Interactively configure and save provider API keys (once per machine)")

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

    if args.command == "init":
        return _cmd_init()
    if args.command == "providers":
        return _cmd_providers()
    if args.command == "costs":
        return _cmd_costs(args.mode)
    if args.command == "run":
        return _cmd_run(args)

    parser.print_help()
    return 1


def _cmd_init() -> int:
    print("Argus setup — configure your provider API keys.")
    print(
        f"Stored in {config_env_path()} (owner-read/write only); "
        "picked up automatically from any directory afterward.\n"
    )

    saved_globally = load_file_env(include_project_dotenv=False)
    to_save: dict[str, str] = {}

    for name, cls in REGISTRY.items():
        key_name = cls.env_key
        print(f"--- {name} ({key_name}) ---  {_KEY_URLS.get(name, '')}")

        existing = saved_globally.get(key_name, "")
        if existing:
            print(f"    Already saved: {mask(existing)}")
            if input("    Replace it? [y/N] ").strip().lower() != "y":
                print()
                continue
        else:
            env_value = os.environ.get(key_name, "")
            if env_value:
                print(f"    Found in your shell environment: {mask(env_value)}")
                if input("    Save it to Argus's global config too? [Y/n] ").strip().lower() != "n":
                    to_save[key_name] = env_value
                    print()
                    continue

        value = getpass(f"    Paste your {key_name} (blank to skip): ").strip()
        if value:
            to_save[key_name] = value
        print()

    if not to_save:
        print("Nothing new to save.")
        return 0

    path = save_keys(to_save)
    print(f"Saved {len(to_save)} key(s) to {path}\n")

    configured = Argus().available_providers()
    print(f"Configured providers: {', '.join(configured) if configured else 'none'}")
    print('Run `argus providers` any time to check status, or `argus run "your query"` to try it.')
    return 0


def _cmd_providers() -> int:
    from pathlib import Path

    from dotenv import dotenv_values

    project_env = dotenv_values(Path.cwd() / ".env")
    global_env = load_file_env(include_project_dotenv=False)

    for name, cls in REGISTRY.items():
        key_name = cls.env_key
        if os.environ.get(key_name):
            status = "configured (shell env)"
        elif project_env.get(key_name):
            status = "configured (./.env)"
        elif global_env.get(key_name):
            status = f"configured ({config_env_path()})"
        else:
            status = f"missing {key_name}"
        modes = ", ".join(m.value for m in cls.supported_modes)
        print(f"  {name:<12} [{status:<38}] modes: {modes}")

    if not Argus().available_providers():
        print('\nNo providers configured yet — run `argus init` to set one up.')
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
