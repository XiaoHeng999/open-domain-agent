"""Enhanced configuration loader — auto-discovery, .env, layered resolution.

Design follows nanobot conventions:
  - Convention over configuration: auto-find config.yaml in project root
  - Layered resolution: defaults < config.yaml < .env < env vars < CLI overrides
  - Zero side-effects on existing config.py — this module wraps around it

Resolution priority (highest wins):
  1. CLI runtime overrides (kwargs passed to load_config)
  2. Environment variables (OPEN_AGENT_* prefix)
  3. .env file (project root or CWD)
  4. config.yaml (explicit --config or auto-discovered)
  5. Pydantic model defaults
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from open_agent.config import AgentConfig
from open_agent.config import load_config as _original_load_config

# Config file names to search for (in priority order)
_CANDIDATE_NAMES = ["config.yaml", "agent.yaml", ".open_agent/config.yaml"]


def _find_project_root() -> Path | None:
    """Walk up from CWD to find the project root (contains pyproject.toml)."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def _find_config_file(explicit_path: str | None = None) -> str | None:
    """Resolve config file: explicit path > auto-discovery."""
    if explicit_path:
        return explicit_path if Path(explicit_path).exists() else None

    search_dirs: list[Path] = [Path.cwd()]
    project_root = _find_project_root()
    if project_root and project_root != Path.cwd():
        search_dirs.append(project_root)

    for search_dir in search_dirs:
        for name in _CANDIDATE_NAMES:
            candidate = search_dir / name
            if candidate.exists():
                return str(candidate)
    return None


def _load_dotenv() -> None:
    """Load .env into os.environ without overriding existing values.

    Searches: CWD/.env, then project_root/.env.
    """
    candidates = [Path.cwd() / ".env"]
    project_root = _find_project_root()
    if project_root and project_root != Path.cwd():
        candidates.append(project_root / ".env")

    env_path = next((p for p in candidates if p.exists()), None)
    if not env_path:
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: str | None = None, **overrides: Any) -> AgentConfig:
    """Load config with auto-discovery and .env support.

    Same signature as the original load_config — drop-in replacement.
    """
    # 1. Load .env first so OPEN_AGENT_* vars are visible to _apply_env_overrides
    _load_dotenv()

    # 2. Resolve config file (explicit or auto-discovered)
    config_path = _find_config_file(path)

    # 3. Delegate to original load_config (yaml + env vars + runtime overrides)
    return _original_load_config(config_path, **overrides)
