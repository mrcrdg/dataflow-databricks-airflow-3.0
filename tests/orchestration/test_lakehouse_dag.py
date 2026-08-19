"""Integrity tests for the lakehouse DAG.

A DAG is a Python file that only fails at parse time, in a scheduler, in
production. ADR 0002 says an artifact nothing exercises gets deleted — this is
what exercises it: the DAG is imported for real, Cosmos renders the dbt project
for real, and the resulting task graph is asserted against.

What this cannot check is that the tasks *do* the right thing; that needs the
191MB dump and four minutes. `airflow dags test lakehouse` is the full run, and
`orchestration/AGENTS.md` records the last verified result.

Skipped unless the orchestration extras are installed — Airflow is opt-in
(`uv sync --group orchestration`) precisely so a plain clone stays small.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Airflow writes a config file and a sqlite database into AIRFLOW_HOME on
# import. Point it at a temp directory before that import happens, or running
# the suite silently creates ~/airflow.
os.environ.setdefault("AIRFLOW_HOME", tempfile.mkdtemp(prefix="airflow-test-"))
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")

# Cosmos caches its `dbt ls` output in an Airflow *Variable*, which means a
# metadata database. Parsing a DAG should not require one, and running
# `airflow db migrate` from a test would be a heavy side effect for an
# integrity check. Turning the cache off costs a few seconds per run and keeps
# this test dependent on nothing but the files in the repo.
os.environ.setdefault("AIRFLOW__COSMOS__ENABLE_CACHE", "False")

pytest.importorskip("airflow", reason="needs `uv sync --group orchestration`")
pytest.importorskip("cosmos", reason="needs `uv sync --group orchestration`")

if shutil.which("dbt") is None:
    pytest.skip("needs `uv sync --group dbt` — Cosmos shells out to dbt to render the DAG",
                allow_module_level=True)

from airflow.models import DagBag  # noqa: E402

DAGS_FOLDER = Path(__file__).resolve().parents[2] / "orchestration" / "airflow_dags"


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    """Parse the DAGs folder once. Cosmos runs `dbt ls` here, so it is slow."""
    return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)


@pytest.fixture(scope="module")
def dag(dagbag: DagBag):
    """The parsed DAG.

    Read straight out of `dagbag.dags` rather than via `get_dag()`, which in
    Airflow 3 goes to the metadata database to check whether the serialised
    version is stale. There is no database here, and parsing a file should not
    need one.
    """
    return dagbag.dags.get("lakehouse")


def test_dags_folder_has_no_import_errors(dagbag: DagBag):
    """The single most valuable DAG test: does the file even load.

    The DAG this replaces would have failed here — it used `schedule_interval`,
    removed in Airflow 3.0, and imported `src.dataflow`, which is not the
    package name.
    """
    assert dagbag.import_errors == {}


def test_the_lakehouse_dag_exists(dag):
    assert dag is not None


def test_schedule_is_none_because_the_source_is_a_static_dump(dag):
    """Not an oversight — see the DAG docstring.

    The dump is an archive file. A daily schedule would re-ingest identical
    bytes every morning and present that as a pipeline.
    """
    assert dag.schedule is None


def test_both_bronze_ingestions_are_present(dag):
    task_ids = set(dag.task_ids)

    assert {"ingest_bronze_posts", "ingest_bronze_users"} <= task_ids


def test_bronze_tasks_are_independent_of_each_other(dag):
    """They read different files and write different tables, so they parallelise.

    Chaining them would double the wall-clock for no reason.
    """
    posts = dag.get_task("ingest_bronze_posts")
    users = dag.get_task("ingest_bronze_users")

    assert users.task_id not in posts.downstream_task_ids
    assert posts.task_id not in users.downstream_task_ids


def test_every_dbt_model_is_its_own_task(dag):
    """The whole reason for Cosmos over a single BashOperator running `dbt build`.

    Per-model tasks mean a failure names the model and a retry re-runs only it.
    """
    task_ids = set(dag.task_ids)

    for model in ("stg_posts", "stg_users", "marts_top_tags", "marts_posts_users"):
        assert f"dbt.{model}.run" in task_ids, f"no run task for {model}"
        assert f"dbt.{model}.test" in task_ids, f"no test task for {model}"


def test_no_dbt_task_starts_before_both_bronze_tables_exist(dag):
    """stg_posts reads one bronze table, stg_users the other, and the mart joins
    them. Every dbt task must therefore sit downstream of both ingestions.

    Asserted over the whole group rather than the two roots, so adding a model
    that accidentally hangs off nothing fails here.
    """
    posts_downstream = dag.get_task("ingest_bronze_posts").get_flat_relative_ids(upstream=False)
    users_downstream = dag.get_task("ingest_bronze_users").get_flat_relative_ids(upstream=False)

    dbt_tasks = {t for t in dag.task_ids if t.startswith("dbt.")}

    assert dbt_tasks <= posts_downstream
    assert dbt_tasks <= users_downstream


def test_every_dbt_task_gets_absolute_paths(dag):
    """Cosmos symlinks the dbt project into a temp dir and runs dbt from there.

    A relative bronze path would resolve under /tmp and delta_scan() would find
    nothing. A relative DuckDB path would create a throwaway database inside
    that temp dir, which is deleted when the task exits — so the run reports
    success and produces no tables. Both fail silently, which is why they are
    pinned here.

    Asserted on the rendered operators rather than on the config object, because
    the operator is what actually runs.
    """
    dbt_tasks = [dag.get_task(t) for t in dag.task_ids if t.startswith("dbt.")]
    assert dbt_tasks, "no dbt tasks were rendered"

    for task in dbt_tasks:
        assert Path(task.project_dir).is_absolute(), task.task_id
        for name, value in task.vars.items():
            assert Path(value).is_absolute(), f"{task.task_id}: {name} is relative"
        assert Path(task.env["DATAFLOW_DUCKDB_PATH"]).is_absolute(), task.task_id
