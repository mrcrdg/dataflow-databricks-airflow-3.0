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
- **Silver + gold (partial)** — dbt reads the Delta table in place via DuckDB
  `delta_scan` (no copy) and builds:
  - `stg_posts` (silver view) — cleaned, typed, tags as an array, post types labelled
  - `marts_top_tags` (gold table) — top-N tags, default 100
- **Tests** — 26 pytest tests + 11 dbt tests, all green. `ruff` clean.
- **Docs** — `AGENTS.md` in every directory, `ROADMAP.md`, `README.md`, and
  `docs/adr/0001` (UTC timezone) + `0002` (delete unexercised artifacts).
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

In priority order. Only the first two are "core"; the rest is polish.

### 1. Users layer → final gold table  (next up)

Completes the data story. `src/dataflow/bronze/users.py` is an empty stub;
`data/ai.stackexchange.com/Users.xml` (21MB) is present.

- `bronze/users.py` + entrypoint + config entry + tests — mirror bronze posts exactly
- Users schema (from the notebook extraction): AboutMe, AccountId, CreationDate,
  DisplayName, DownVotes, Id, LastAccessDate, Location, Reputation, UpVotes,
  Views, WebsiteUrl
- `stg_users` (silver view)
- `marts_posts_users` (gold table): `stg_posts LEFT JOIN stg_users ON owner_user_id = user_id`
  - **Fixes to apply during the port** (found in review / notebook analysis):
    - keep `owner_user_id` in the output (the notebook dropped it, so a missed
      join lost the id entirely)
    - add a `unique` test on `stg_users.user_id` — a duplicate would fan out the
      join and break the one-row-per-post grain

### 2. Airflow 3 + Cosmos orchestration  (the finale)

Install group already exists: `uv sync --group orchestration` (Airflow 3.2.0).

- Fix `orchestration/airflow_dags/bronze_posts_pipeline.py` — it uses
  `schedule_interval` (removed in Airflow 3.0 → `schedule`), builds its own
  Spark session without Delta, and imports `src.dataflow` (should be `dataflow`).
- DAG shape: bronze (PythonOperator → `pipelines.bronze_posts.main`) → dbt models
  rendered per-model by Cosmos.

### 3. Polish

- **CI** (GitHub Actions): run `pytest` + `dbt build` on a fixture on every push.
- **More ADRs**: Spark-for-bronze-only, why DuckDB/local-first. (The Spark/dbt
  boundary reasoning is currently only in `AGENTS.md`.)
- **README**: refresh once users + Airflow land.

## Deliberately shelved (see ROADMAP.md)

- Databricks as production target (dbt makes it an adapter swap).
- LLM enrichment layer (a project of its own — determinism, caching, cost, evals).
- Dockerfile (deleted; returns with CI that builds it — see ADR 0002).

## How to run everything

```bash
uv sync --group dbt                              # deps (add --group orchestration for Airflow)
uv pip install -e . --no-deps                    # make `dataflow` importable
python pipelines/bronze_posts.py                 # bronze: Posts.xml -> Delta (26,764 rows)
dbt build --project-dir dbt --profiles-dir dbt   # silver + gold + tests
pytest                                           # 26 tests
ruff check .                                      # lint
```
