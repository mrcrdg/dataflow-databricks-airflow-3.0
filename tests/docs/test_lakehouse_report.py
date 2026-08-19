"""Checks that docs/lakehouse-report.html still describes this repo.

The report is a written artifact, and this project has been bitten three times
by written artifacts that nobody checked — a config naming a CSV that never
existed, a README listing deleted files, a Dockerfile that could not build. ADR
0002 says an artifact must be exercised by something automated or be deleted.
This is what exercises it.

What is asserted here is the report's **structural** claims: the models, entry
points, ADRs and row-count baselines it names must match what is on disk. What
is deliberately *not* asserted is its measured figures — run durations, test
counts — because the report is a dated snapshot and says so in its footer. A
snapshot that was true when taken is a record, not drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "docs" / "lakehouse-report.html"


@pytest.fixture(scope="module")
def report() -> str:
    return REPORT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# It has to open as a document, not a fragment
# ---------------------------------------------------------------------------


def test_report_exists():
    assert REPORT.is_file(), f"missing: {REPORT}"


def test_report_is_a_standalone_html_document(report):
    """It lives in the repo, so a browser must be able to open it from disk.

    The published-artifact form of this page is a fragment — the host wraps it.
    A file on disk gets no wrapper: without a doctype it renders in quirks mode,
    and without a charset the punctuation decodes as mojibake.
    """
    head = report[:400].lower()

    assert head.startswith("<!doctype html>")
    assert 'charset="utf-8"' in head
    assert report.rstrip().endswith("</html>")


def test_report_needs_no_local_assets(report):
    """No build step, no asset folder, nothing to break when the file moves.

    Google Fonts is the one remote host allowed, and it degrades to the declared
    fallback stack rather than breaking the page.
    """
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', report)
    non_fonts = [u for u in external if "fonts.googleapis.com" not in u and "fonts.gstatic.com" not in u]

    assert non_fonts == [], f"report depends on external assets: {non_fonts}"
    assert "<script" not in report.lower()


# ---------------------------------------------------------------------------
# Structural claims — these must track the code
# ---------------------------------------------------------------------------


def _dbt_models() -> set[str]:
    return {p.stem for p in (REPO_ROOT / "dbt" / "models").rglob("*.sql")}


def test_every_dbt_model_is_described(report):
    """Adding a model without mentioning it leaves the report quietly incomplete."""
    missing = sorted(m for m in _dbt_models() if m not in report)

    assert missing == [], f"models absent from the report: {missing}"


def test_the_report_names_no_model_that_does_not_exist(report):
    """The other direction: a renamed or deleted model must not linger here."""
    named = set(re.findall(r"\b(?:stg|marts)_[a-z_]+", report))
    phantom = sorted(named - _dbt_models())

    assert phantom == [], f"report names models that do not exist: {phantom}"


def test_every_pipeline_entrypoint_is_documented(report):
    """The report tells a reader how to run the project. That list must be whole."""
    entrypoints = {p.name for p in (REPO_ROOT / "pipelines").glob("*.py")}
    missing = sorted(e for e in entrypoints if e not in report)

    assert missing == [], f"entrypoints absent from the report: {missing}"


def test_every_adr_is_referenced_and_every_reference_resolves(report):
    """ADRs are the project's record of *why*. The report cites them by number."""
    on_disk = {p.name[:4] for p in (REPO_ROOT / "docs" / "adr").glob("*.md")}
    cited = set(re.findall(r"ADR\s+(\d{4})", report))

    assert on_disk - cited == set(), f"ADRs the report never cites: {sorted(on_disk - cited)}"
    assert cited - on_disk == set(), f"report cites missing ADRs: {sorted(cited - on_disk)}"


def test_row_count_baselines_agree_with_the_project_guide(report):
    """One set of numbers, asserted in two places.

    AGENTS.md holds the baselines a refactor is checked against. If the report
    disagreed with it, one of them would be lying and a reader would have no way
    to tell which.
    """
    guide = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    baselines = set(re.findall(r"\b\d{2},\d{3}\b", guide))

    assert baselines, "no baseline row counts found in AGENTS.md"

    missing = sorted(b for b in baselines if b not in report)
    assert missing == [], f"baselines in AGENTS.md but not in the report: {missing}"
