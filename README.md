# Medallion Lakehouse — Stack Exchange AI dump

[![CI](https://github.com/mrcrdg/dataflow-databricks-airflow-3.0/actions/workflows/ci.yml/badge.svg)](https://github.com/mrcrdg/dataflow-databricks-airflow-3.0/actions/workflows/ci.yml)

A bronze → silver → gold data pipeline over the
[ai.stackexchange.com](https://archive.org/details/stackexchange) archive.
Raw XML in, analytics tables out.

**Runs locally. No cloud account, no credentials, no paid services.**

```
Posts.xml ──┐
            ├─[Spark]──> bronze (Delta) ──[dbt]──> silver ──[dbt]──> gold
Users.xml ──┘                                       |
                                             [Airflow + Cosmos]
```

## The design decision

**Spark handles ingestion. dbt handles everything downstream.**

Parsing XML is the one job dbt cannot do — dbt transforms tables that already
exist, it does not read files. So Spark earns its place at bronze and nowhere
else.

Once the data is a table, the work is SQL. dbt gives tests, lineage, docs and
incremental logic for free; re-implementing those in PySpark would be rebuilding
dbt badly.

That boundary is the whole architecture. Everything else follows from it.
Written up in [ADR 0004](docs/adr/0004-spark-only-at-bronze.md).

## Status

| Layer | State |
|---|---|
| Bronze — XML → Delta | **working** — 26,764 posts, 71,811 users, tested |
| Silver — `stg_posts`, `stg_users` | **working** — dbt views over the Delta tables |
| Gold — `marts_top_tags`, `marts_posts_users` | **working** — dbt tables |
| Orchestration — Airflow 3 + Cosmos | **working** — 12 tasks, verified end to end |

65 pytest tests and 20 dbt tests, all green, and CI runs every one of them on
every push — including the dbt models, built from the committed fixtures. Eight
of the pytest tests import Airflow and skip unless the orchestration extras are
installed.

Scope decisions, including what was deliberately left out and why, are in
[ROADMAP.md](ROADMAP.md).

**New here?** [`docs/lakehouse-report.html`](docs/lakehouse-report.html) explains
the whole project from first principles — what it is, how the data moves, what
works and what is left — with every piece of jargon defined. Open it in a
browser; it is a single self-contained file with no build step.

## Quickstart

```bash
uv sync --group dbt                 # install dependencies
uv pip install -e . --no-deps       # make `dataflow` importable
```

Download the [ai.stackexchange.com dump](https://archive.org/details/stackexchange)
and extract it to `data/ai.stackexchange.com/`, then:

```bash
python pipelines/bronze_posts.py    # ingest Posts.xml -> Delta
python pipelines/bronze_users.py    # ingest Users.xml -> Delta
dbt build --project-dir dbt --profiles-dir dbt   # silver + gold + dbt tests
pytest                              # tests, ~2min
ruff check .                        # lint
```

To run the whole thing as one orchestrated DAG instead:

```bash
uv sync --group dbt --group orchestration
export AIRFLOW_HOME=~/airflow-dataflow
export AIRFLOW__CORE__DAGS_FOLDER=$PWD/orchestration/airflow_dags
airflow db migrate && airflow dags reserialize
airflow dags test lakehouse         # bronze x2, then every dbt model as a task
```

The pytest suite runs against small fixtures cut from the real dump, so it works
without downloading the 191MB archive. `dbt build` needs bronze tables to read,
so the commands above need the real dump — but you can build the whole dbt
project on the fixtures instead, which is exactly what CI does:

```bash
DATAFLOW_CONFIG=configs/pipeline.ci.yaml python pipelines/bronze_posts.py
DATAFLOW_CONFIG=configs/pipeline.ci.yaml python pipelines/bronze_users.py
DATAFLOW_DUCKDB_PATH=$PWD/ci.duckdb dbt build --project-dir dbt --profiles-dir dbt \
  --vars "{bronze_posts_path: $PWD/ci-warehouse/bronze.db/posts, \
           bronze_users_path: $PWD/ci-warehouse/bronze.db/users}"
```

## Layout

```
src/dataflow/       transformation logic — pure functions, no I/O
  bronze/           XML ingestion — posts, users
  common/           Spark factory, config loader, logging
pipelines/          entrypoints — wiring only, one per job
configs/            pipeline.yaml, the only place paths and tables are declared
dbt/                silver + gold models, seeds and tests
tests/              test suite + 5-row fixtures cut from the real dump
notebooks/          frozen Databricks prototypes — not production code
orchestration/      the Airflow 3 + Cosmos DAG
docs/               the project report, plus architecture decision records
```

Each directory has an `AGENTS.md` explaining what it is for and the rule that
governs it.

## Why DuckDB and not Databricks

This was originally built on Databricks (the notebooks are still here). It was
rewritten to run locally because **a portfolio project that needs cloud
credentials is a project nobody can run** — including whoever is reviewing it.

dbt makes this a swap of adapter rather than a rewrite: `dbt-duckdb` locally,
`dbt-databricks` in the cloud, same models. Databricks remains the documented
production target. Written up in
[ADR 0005](docs/adr/0005-duckdb-local-first.md); scope in
[ROADMAP.md](ROADMAP.md).

## On scale, honestly

The dataset is 191MB, 26,764 posts and 71,811 users. **Spark is not required at
this size** — a single-node engine would be faster.

It is used because this project is a scale-model of a Spark workload, and the
ingestion patterns are the point: explicit schemas, a session factory, Delta as
the table format, transformations isolated from I/O. Those patterns are what
transfer to a real cluster. The data volume is not.

## A bug worth mentioning

The Stack Exchange dump stores naive timestamps that are UTC. Spark's default
session timezone is the host machine's, so bronze was reading them as local time
and storing every timestamp three hours early — across all 26,764 rows.

Nothing failed. Row counts were correct. It surfaced only when validating that
DuckDB could read the Delta table, where the offset had to become explicit.

The reproducibility consequence mattered more than the correctness one: the same
input produced different output depending on who ran it. Written up in
[ADR 0001](docs/adr/0001-pin-spark-session-timezone-to-utc.md).

## How I used AI

AI-assisted, and worth being specific about where:

- **AI-written:** most implementation code, test scaffolding, docstrings, the
  `AGENTS.md` guides, commit messages.
- **Human-owned:** the Spark/dbt boundary, the decision to go local-first, what
  to cut (Kubernetes, the portability claims), and the reasoning in each ADR.
- **Reviewed by AI, then verified independently:** an AI code review flagged five
  issues on the first PR, three of which were documentation and packaging
  drifting away from the code. Useful — but the checks that actually catch
  correctness problems here are the test suite and the 26,764-row baseline,
  because they do not share the author's assumptions.

The timezone bug is the honest illustration: the model that wrote the ingestion
code also reviewed it, and missed it. What caught it was reading the same data
through a second engine.

## Data source

[Stack Exchange data dump](https://archive.org/details/stackexchange),
ai.stackexchange.com, CC BY-SA. Not committed to this repo.
