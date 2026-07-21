"""Configuration loading for pipeline jobs.

Jobs read their source paths, table names and write modes from
`configs/pipeline.yaml` rather than hardcoding them, so the same code can point
at a test fixture, a local dump, or cloud storage without being edited.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Repo root: src/dataflow/common/config.py -> up 3 -> project root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "configs" / "pipeline.yaml"


def config_path() -> Path:
    """Path to the active config file. Override with DATAFLOW_CONFIG."""
    override = os.environ.get("DATAFLOW_CONFIG")
    return Path(override) if override else _DEFAULT_CONFIG_PATH


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load and parse the pipeline config."""
    resolved = Path(path) if path is not None else config_path()
    if not resolved.is_file():
        raise FileNotFoundError(f"Pipeline config not found: {resolved}")

    with resolved.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def job_config(layer: str, job: str, path: str | Path | None = None) -> dict[str, Any]:
    """Return the config block for a single job, e.g. ("bronze", "posts")."""
    config = load_config(path)
    try:
        return config[layer][job]
    except (KeyError, TypeError):
        raise KeyError(f"No config for '{layer}.{job}' in {path or config_path()}") from None


def spark_config(path: str | Path | None = None) -> dict[str, Any]:
    """Return the `spark:` block, or an empty dict if absent."""
    return load_config(path).get("spark", {})
