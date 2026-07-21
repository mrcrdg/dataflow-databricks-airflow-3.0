# AGENTS.md — project guide

Orientation for anyone (human or AI agent) working in this repo. Directory-level
`AGENTS.md` files add detail; this one covers the whole project.

## What this project is

A medallion lakehouse over the [ai.stackexchange.com](https://archive.org/details/stackexchange)
data dump. Raw XML in, analytics tables out.

```
Posts.xml ──[Spark]──> bronze (Delta) ──[dbt]──> silver ──[dbt]──> gold
                                                     |
                                              [Airflow + Cosmos]
```

## The one design decision that explains the layout

**Spark handles ingestion. dbt handles everything downstream.**

Parsing XML is the one job dbt cannot do — dbt only transforms tables that
already exist. So Spark earns its place at bronze and nowhere else. Once data is
a table, the work is SQL, and dbt gives tests, lineage, docs and incremental
logic for free. Re-implementing those in PySpark would be rebuilding dbt badly.

## Runtime target

**DuckDB, locally.** The project must be runnable by anyone who clones it — no
cloud credentials, no paid account. Databricks was the original prototype
environment (see `notebooks/`) and remains the documented production target, but
is deliberately out of scope. See `ROADMAP.md`.

## Conventions

- **Business logic lives in `src/dataflow/`, never in entrypoints or notebooks.**
  Entrypoints wire things together; they hold no transformation logic.
- **Transformations are pure functions**: `DataFrame -> DataFrame`, no I/O. This
  is what makes them unit-testable, and it is not negotiable.
- **Nothing is hardcoded that belongs in `configs/pipeline.yaml`** — paths, table
  names, write modes.
- **One way to run each job.** If you find two entrypoints for the same job,
  that is a bug to fix, not a feature.
- Sessions come from `dataflow.common.spark.get_spark()`. Never call
  `SparkSession.builder` directly outside that module.
- Logging via `dataflow.common.logging.get_logger()`, `%s` placeholders, no
  f-strings in log calls.

## Commands

```bash
uv sync                              # install dependencies
pip install -e . --no-deps           # make `dataflow` importable
python pipelines/bronze_posts.py     # run bronze ingestion
pytest                               # run tests
ruff check .                         # lint
```

## Known baseline

Bronze ingestion of `Posts.xml` produces **26,764 rows**. Any refactor that
changes this number has changed behaviour — treat it as a regression test.

## Scale, stated honestly

The dataset is ~191MB and 26,764 posts. Spark is not required at this size; a
single-node engine would be faster. It is used because this project is a
scale-model of a Spark workload and the ingestion patterns are the point. Do not
pretend the data is big — the honest framing is the defensible one.

## Do not

- Add abstraction layers with a single caller (`common/io.py` was deleted for
  exactly this reason).
- Reintroduce "runs on Databricks, Airflow and Kubernetes" portability claims.
  One target, done properly.
- Put production logic in `notebooks/`. They are frozen prototypes.
