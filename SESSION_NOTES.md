# Session notes

Running state of the work, so any session (or person) can resume without the
chat history. Update this at the end of a working session. For *why* decisions
were made, see `docs/adr/`; for scope, see `ROADMAP.md`.

_Last updated: 2026-08-19_

## Where things are

The project was a stalled scaffold. It is now a working, tested, local-first
lakehouse: **bronze (Spark/Delta) → silver + gold (dbt/DuckDB)**, runnable by
anyone who clones it.

### Done and verified

- **Bronze** — `python pipelines/bronze_posts.py` ingests `Posts.xml` to a Delta
  table. 26,764 rows (the regression baseline). Single entrypoint, config-driven.
- **Bronze users** — `python pipelines/bronze_users.py` ingests `Users.xml`.
  71,811 rows (the second baseline).
- **Silver + gold** — dbt reads the Delta tables in place via DuckDB
  `delta_scan` (no copy) and builds:
  - `stg_posts` (silver view) — cleaned, typed, tags as an array, post types labelled
  - `stg_users` (silver view) — cleaned, typed, blank strings collapsed to NULL
  - `marts_top_tags` (gold table) — top-N tags, default 100
  - `marts_posts_users` (gold table) — one row per post + its author, 26,764 rows
- **Tests** — 40 pytest tests + 20 dbt tests, all green. `ruff` clean.
- **Docs** — `AGENTS.md` in every directory, `ROADMAP.md`, `README.md`, and
  `docs/adr/0001` (UTC timezone) + `0002` (delete unexercised artifacts).
- **Users layer (2026-08-19)** — bronze users, `stg_users` and
  `marts_posts_users`, with both notebook defects fixed during the port
  (`owner_user_id` kept alongside `user_id`; `unique` test on
  `stg_users.user_id` guarding the grain). `author_status` distinguishes
  resolved / unresolved / anonymous authors.
- **Housekeeping (2026-08-19)** — deleted the empty `src/dataflow/silver/`,
  `src/dataflow/gold/`, `pipelines/silver_posts.py` and
  `pipelines/gold_analytics.py` stubs (ADR 0002: nothing exercised them, and the
  port went to dbt, not Python). `ROADMAP.md` and the affected `AGENTS.md` files
  now match reality.

### Git / GitHub state — read this carefully

- Branch: **`refactor/local-first-lakehouse`**.
- **PR #1 is MERGED into `main`** — everything *through the review fixes*
  (`fa6c4c8`).
- The **dbt increment (`6d69061`)** landed after PR #1 merged, so it needs a
  second PR from the same branch. That PR is open (see GitHub) and also carries
  the housekeeping commit below.
- Local `main` lags `origin/main`; `git fetch && git checkout main && git pull`
  before branching from it.

## What's left

In priority order. Only the first is "core"; the rest is polish.

### 1. Airflow 3 + Cosmos orchestration  (the finale — next up)

Install group already exists: `uv sync --group orchestration` (Airflow 3.2.0).

- Fix `orchestration/airflow_dags/bronze_posts_pipeline.py` — it uses
  `schedule_interval` (removed in Airflow 3.0 → `schedule`), builds its own
  Spark session without Delta, and imports `src.dataflow` (should be `dataflow`).
- DAG shape: two bronze PythonOperators (`pipelines.bronze_posts.main`,
  `pipelines.bronze_users.main`) → dbt models rendered per-model by Cosmos.
  The two bronze tasks are independent and can run in parallel; every dbt model
  depends on both only through the source it reads, so let Cosmos work that out
  rather than forcing a linear chain.

### 2. Polish

- **CI** (GitHub Actions): run `pytest` + `dbt build` on a fixture on every push.
- **More ADRs**: Spark-for-bronze-only, why DuckDB/local-first. (The Spark/dbt
  boundary reasoning is currently only in `AGENTS.md`.)
- **README**: refreshed for the users layer; refresh again once Airflow lands.

## Deliberately shelved (see ROADMAP.md)

- Databricks as production target (dbt makes it an adapter swap).
- LLM enrichment layer (a project of its own — determinism, caching, cost, evals).
- Dockerfile (deleted; returns with CI that builds it — see ADR 0002).

## How to run everything

```bash
uv sync --group dbt                              # deps (add --group orchestration for Airflow)
uv pip install -e . --no-deps                    # make `dataflow` importable
python pipelines/bronze_posts.py                 # bronze: Posts.xml -> Delta (26,764 rows)
python pipelines/bronze_users.py                 # bronze: Users.xml -> Delta (71,811 rows)
dbt build --project-dir dbt --profiles-dir dbt   # silver + gold + 20 dbt tests
pytest                                           # 40 tests, ~2min
ruff check .                                     # lint
```
