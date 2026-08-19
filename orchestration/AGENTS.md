# orchestration — scheduling

How jobs get triggered. No logic, no wiring — those live in `src/dataflow/` and
`pipelines/`. A DAG task is a thin call to a `pipelines/*.main()`.

## The DAG

`airflow_dags/lakehouse.py`, on **Airflow 3.2** with
**[Cosmos](https://www.astronomer.io/docs/learn/airflow-dbt/) 1.15**.

```
Posts.xml ──[ingest_bronze_posts]──┐
                                   ├──> dbt task group (12 tasks total)
Users.xml ──[ingest_bronze_users]──┘
```

The two ingestions are independent — different files, different tables — so
they run in parallel. Everything downstream is dbt.

## Why Cosmos rather than one `dbt build` task

Cosmos renders **each dbt model as its own Airflow task**, with its tests as a
separate task after it:

```
dbt.post_types.seed        dbt.stg_users.run          dbt.marts_top_tags.run
dbt.post_types.test        dbt.stg_users.test         dbt.marts_top_tags.test
dbt.stg_posts.run          dbt.marts_posts_users.run
dbt.stg_posts.test         dbt.marts_posts_users.test
```

A single `BashOperator` running `dbt build` would be one green or red box. This
gives per-model retries, per-model timing, and the dbt lineage graph visible in
the Airflow UI. When model 7 of 12 fails you retry model 7.

## The thing that will bite you: paths

**Cosmos symlinks the dbt project into a temporary directory and runs dbt from
there.** Every relative path in the project resolves against `/tmp`, not the
repo root. Two consequences, both silent:

- `delta_scan('spark-warehouse/bronze.db/posts')` finds nothing
- `path: dataflow.duckdb` creates a throwaway database that is deleted with the
  temp directory — **the run succeeds and produces no tables**

So the DAG passes absolute paths explicitly: `dbt_vars` for the two bronze Delta
paths, and `env_vars` for `DATAFLOW_DUCKDB_PATH`, which `profiles.yml` reads
with a relative default so the plain CLI is unaffected.

The same class of problem applies to the bronze tasks — Airflow does not run
from the repo root either. That is handled in `dataflow.common.config`:
`resolve_path()` anchors config paths to the project root rather than the cwd.

## Schedule: `None`, deliberately

The source is a static archive dump. A daily schedule would re-ingest identical
bytes every morning and present that as a pipeline. Trigger it when a new dump
is downloaded, which is the real cadence.

This is the same reasoning that keeps streaming out of scope — see `ROADMAP.md`.

## Verifying it

```bash
uv sync --group dbt --group orchestration
export AIRFLOW_HOME=~/airflow-dataflow          # anywhere writable
export AIRFLOW__CORE__DAGS_FOLDER=$PWD/orchestration/airflow_dags
airflow db migrate
airflow dags reserialize
airflow dags test lakehouse
```

**Last verified: 2026-08-19** — 12/12 tasks succeeded, DAG run 240s, all dbt
tests green, and the row counts in `AGENTS.md` unchanged afterwards. The DuckDB
file written was the project's, not a temp one; that check is the point, because
the failure mode it rules out reports success.

`tests/orchestration/test_lakehouse_dag.py` is the automated half: it parses the
DAG for real, lets Cosmos render the dbt project for real, and asserts on the
resulting graph. It runs in the normal `pytest` suite and skips cleanly when the
orchestration extras are not installed. What it cannot check is that the tasks
*do* the right thing — that needs the full run above.

## What replaced what

`bronze_posts_pipeline.py` is **deleted**. It never ran: `schedule_interval=`
(removed in Airflow 3.0), a bare `SparkSession.builder` with no Delta
extensions, and `import src.dataflow` instead of `dataflow`. Recorded here
rather than kept as a broken file — see `docs/adr/0002`.

## databricks_jobs/

Empty, and deliberately so. Databricks is the documented production target but
is out of scope for now.
