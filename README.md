# Medallion Lakehouse — Stack Exchange AI dump

A bronze → silver → gold data pipeline over the
[ai.stackexchange.com](https://archive.org/details/stackexchange) archive.
Raw XML in, analytics tables out.

**Runs locally. No cloud account, no credentials, no paid services.**

```
Posts.xml ──[Spark]──> bronze (Delta) ──[dbt]──> silver ──[dbt]──> gold
                                                    |
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

## Status

| Layer | State |
|---|---|
| Bronze — XML → Delta | **working**, 26,764 rows, tested |
| Silver — cleaning, tags, post types | logic exists in `notebooks/`, being ported to dbt |
| Gold — posts×users, top tags | logic exists in `notebooks/`, being ported to dbt |
| Orchestration — Airflow 3 + Cosmos | not started |

Scope decisions, including what was deliberately left out and why, are in
[ROADMAP.md](ROADMAP.md).

## Quickstart

```bash
uv sync                             # install dependencies
uv pip install -e . --no-deps       # make `dataflow` importable
```

Download the [ai.stackexchange.com dump](https://archive.org/details/stackexchange)
and extract it to `data/ai.stackexchange.com/`, then:

```bash
python pipelines/bronze_posts.py    # ingest Posts.xml -> Delta
pytest                              # tests, ~60s
ruff check .                        # lint
```

The test suite runs against a 3.5KB fixture, so it works without downloading the
191MB dump.

## Layout

```
src/dataflow/       transformation logic — pure functions, no I/O
  bronze/           XML ingestion
  common/           Spark factory, config loader, logging
pipelines/          entrypoints — wiring only, one per job
configs/            pipeline.yaml, the only place paths and tables are declared
tests/              test suite + a 5-row fixture from the real dump
notebooks/          frozen Databricks prototypes — not production code
orchestration/      Airflow DAGs (not yet working)
docs/adr/           architecture decision records
```

Each directory has an `AGENTS.md` explaining what it is for and the rule that
governs it.

## Why DuckDB and not Databricks

This was originally built on Databricks (the notebooks are still here). It was
rewritten to run locally because **a portfolio project that needs cloud
credentials is a project nobody can run** — including whoever is reviewing it.

dbt makes this a swap of adapter rather than a rewrite: `dbt-duckdb` locally,
`dbt-databricks` in the cloud, same models. Databricks remains the documented
production target. See [ROADMAP.md](ROADMAP.md).

## On scale, honestly

The dataset is 191MB and 26,764 posts. **Spark is not required at this size** — a
single-node engine would be faster.

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
