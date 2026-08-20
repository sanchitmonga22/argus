"""
User-level config storage for provider API keys.

Argus is a pip-installed CLI that gets run from arbitrary directories, so
relying on python-dotenv's cwd/frame-based `.env` auto-discovery is
fragile — it's designed for "run from your project root," not "run from
anywhere." Instead, keys are looked up in this priority order (highest
first):

  1. Real environment variables (`export EXA_API_KEY=...`)
  2. `./.env` in the current directory — project-local override
  3. `~/.config/argus/.env` (or the platform equivalent) — global config,
     written once by `argus init` and picked up from anywhere afterward

`argus init` writes only to the global file, chmod'd 600 since it holds
secrets.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from dotenv import dotenv_values


def config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "argus"


def config_env_path() -> Path:
    return config_dir() / ".env"


def load_file_env(include_project_dotenv: bool = True) -> dict[str, str]:
    """
    File-sourced values only — does NOT include real environment variables.
    Project `.env` (if present) overrides the global config file. Callers
    should still check `os.environ` themselves at a higher priority than
    this.
    """
    merged: dict[str, str] = {}

    global_path = config_env_path()
    if global_path.exists():
        merged.update({k: v for k, v in dotenv_values(global_path).items() if v})

    if include_project_dotenv:
        project_path = Path.cwd() / ".env"
        if project_path.exists():
            merged.update({k: v for k, v in dotenv_values(project_path).items() if v})

    return merged


def save_keys(keys: dict[str, str]) -> Path:
    """
    Merge non-empty `keys` into the global config file, creating it (and
    its parent directory) if needed, and chmod it to owner-read/write only.
    Existing keys not present in `keys` are left untouched.
    """
    path = config_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = dotenv_values(path) if path.exists() else {}
    merged = {**existing, **{k: v for k, v in keys.items() if v}}

    lines = [f"{k}={v}" for k, v in merged.items() if v]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600

    return path


def mask(value: str) -> str:
    """Show just enough of a secret to recognize it without exposing it."""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"
