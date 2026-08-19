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

CONFIG_ENV_VAR = "DATAFLOW_CONFIG"
_CONFIG_RELATIVE_PATH = Path("configs") / "pipeline.yaml"


def _search_upwards(start: Path) -> Path | None:
    """Walk up from `start` looking for configs/pipeline.yaml."""
    for directory in (start, *start.parents):
        candidate = directory / _CONFIG_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    return None


def config_path() -> Path:
    """Locate the active config file.

    Resolution order:

    1. The DATAFLOW_CONFIG environment variable, if set. This is the escape
       hatch for deployments and for tests pointing at a fixture.
    2. Search upwards from this module's location — finds it in a normal
       source checkout or an editable install.
    3. Search upwards from the current working directory — covers the case
       where the package is installed non-editable (into site-packages, where
       there is no repo above it) but the process runs from the project.

    Deliberately not a fixed `parents[N]` hop: that only works for one install
    layout, and fails confusingly under any other.
    """
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override)

    found = _search_upwards(Path(__file__).resolve().parent) or _search_upwards(Path.cwd().resolve())
    if found is not None:
        return found

    raise FileNotFoundError(
        f"Could not locate {_CONFIG_RELATIVE_PATH} by searching upwards from "
        f"{Path(__file__).resolve().parent} or {Path.cwd().resolve()}. "
        f"Set {CONFIG_ENV_VAR} to point at it explicitly."
    )


def project_root(path: str | Path | None = None) -> Path:
    """The directory the config's relative paths are anchored to.

    `configs/pipeline.yaml` lives one level below it, so the root is the config
    file's grandparent.
    """
    resolved = Path(path) if path is not None else config_path()
    return resolved.resolve().parent.parent


def resolve_path(value: str, config: str | Path | None = None) -> str:
    """Make a config path absolute, anchored at the project root.

    Paths in `pipeline.yaml` are written relative to the repo root, because that
    is the readable form and the form a reader can check against `ls`. Resolving
    them against the *current working directory* instead would mean a job only
    runs when launched from the root — fine from the CLI, broken under Airflow,
    which sets its own cwd. Anchoring here makes the two agree.

    An absolute path in the config is returned unchanged, which is the escape
    hatch for a deployment whose data lives outside the repo.
    """
    candidate = Path(value)
    if candidate.is_absolute():
        return str(candidate)
    return str(project_root(config) / candidate)


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
        # Report where we looked; a missing job and a wrong config file look
        # identical from the caller's side otherwise.
        location = path if path is not None else config_path()
        raise KeyError(f"No config for '{layer}.{job}' in {location}") from None


def spark_config(path: str | Path | None = None) -> dict[str, Any]:
    """Return the `spark:` block, or an empty dict if absent."""
    return load_config(path).get("spark", {})
