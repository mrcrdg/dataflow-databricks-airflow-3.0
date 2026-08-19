# AGENTS.md — project guide

Orientation for anyone (human or AI agent) working in this repo. Directory-level
`AGENTS.md` files add detail; this one covers the whole project.

## What this project is

A medallion lakehouse over the [ai.stackexchange.com](https://archive.org/details/stackexchange)
data dump. Raw XML in, analytics tables out.

```
Posts.xml ──┐
            ├─[Spark]──> bronze (Delta) ──[dbt]──> silver ──[dbt]──> gold
Users.xml ──┘                                        |
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
- **Paths from config go through `resolve_path()`.** They are written relative
  to the repo root; resolving them against the current directory would work from
  the CLI and break under Airflow, which runs from elsewhere.
- Logging via `dataflow.common.logging.get_logger()`, `%s` placeholders, no
  f-strings in log calls.

## Decision points — required format

**Never ask a yes/no question without first stating the trade-off.**

Anyone being asked to decide is usually skimming, and often does not hold the
same context as whoever is asking. A bare "shall I proceed?" pushes the work of
reconstructing that context onto the reader, who is the person least equipped to
do it. The implications matter at every step.

Before any yes/no question, give:

1. **What changed** — plain language, no jargon, no file dumps.
2. **What it means** — why it matters in practice.
3. **The consequence of each option** — including what happens if the answer is
   no, and what is hard to undo.

Recommend one option and say why. A decision framed without a recommendation is
just the work handed back.

> **What changed:** `clean_columns` now strips only leading underscores instead
> of all underscores.
> **What it means:** identical output for today's data — no source column has an
> internal underscore — but a column like `user_id` would survive intact where
> before it became `userid`.
> **If yes:** behaviour is pinned by a test; safe.
> **If no:** the old version stays; it works now but would silently mangle names
> if the source schema ever changes.
> **Recommendation:** yes — same result today, fewer surprises later.

This applies to commits, deletions, dependency changes, and schema changes —
anything not trivially reversible. Deletions especially: say what is lost and how
to get it back.

## Commands

```bash
uv sync --group dbt                  # install dependencies
uv pip install -e . --no-deps        # make `dataflow` importable
python pipelines/bronze_posts.py     # bronze: Posts.xml -> Delta
python pipelines/bronze_users.py     # bronze: Users.xml -> Delta
dbt build --project-dir dbt --profiles-dir dbt   # silver + gold + dbt tests
pytest                               # run tests
ruff check .                         # lint

# the same pipeline as one orchestrated DAG (needs --group orchestration)
airflow dags test lakehouse          # see orchestration/AGENTS.md for setup
```

## CI

`.github/workflows/ci.yml` runs on every pull request: `ruff`, `pytest`, then
the **full dbt project** — built against bronze tables that CI ingests from the
committed XML fixtures using `configs/pipeline.ci.yaml`.

The point is that nothing generated is committed. A pre-built Delta fixture
would be an artifact nothing regenerates, free to drift away from what
`bronze/posts.py` actually writes. See `docs/adr/0002`.

Useful side effect: the fixtures reference two user ids the users fixture does
not contain, so CI exercises the `author_status = 'unresolved'` branch, which
the real dump never produces.

## Known baselines

Row counts that pin behaviour. Any refactor that changes one of these has
changed behaviour — treat them as regression tests.

| Table | Rows |
|---|---|
| `bronze.posts` | 26,764 |
| `bronze.users` | 71,811 |
| `marts_posts_users` | 26,764 — one row per post; a different number means the join fanned out |

## Scale, stated honestly

The dataset is ~191MB, 26,764 posts and 71,811 users. Spark is not required at
this size; a single-node engine would be faster. It is used because this project
is a scale-model of a Spark workload and the ingestion patterns are the point. Do
not pretend the data is big — the honest framing is the defensible one.

## Do not

- Add abstraction layers with a single caller (`common/io.py` was deleted for
  exactly this reason).
- Reintroduce "runs on Databricks, Airflow and Kubernetes" portability claims.
  One target, done properly.
- Put production logic in `notebooks/`. They are frozen prototypes.
