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
- **Orchestration** — `orchestration/airflow_dags/lakehouse.py` on Airflow 3.2 +
  Cosmos 1.15. Two parallel bronze tasks, then every dbt model as its own task
  (12 tasks total). Verified with `airflow dags test lakehouse`: 12/12 succeeded,
  240s, row counts unchanged.
- **CI** — `.github/workflows/ci.yml`, green on PR #3 in 2m18s. On every PR:
  `ruff`, `pytest`, then real
  bronze ingestion from the committed XML fixtures (`configs/pipeline.ci.yaml`)
  and a full `dbt build` against the result, followed by an assertion on the row
  counts. Nothing generated is committed. The fixture join covers the
  `unresolved` author branch that the real dump never produces.
- **Project report** — `docs/lakehouse-report.html`, a self-contained page
  explaining the project from first principles for a reader seeing it cold:
  glossary, three diagrams, status, what is left. `tests/docs/` asserts its
  structural claims against the repo so it cannot drift; its measured figures
  are a dated snapshot and are not re-checked.
- **Tests** — 65 pytest tests + 20 dbt tests, all green. `ruff` clean.
- **Docs** — `AGENTS.md` in every directory, `ROADMAP.md`, `README.md`, and
  `docs/adr/0001` (UTC timezone), `0002` (delete unexercised artifacts),
  `0003` (resolve config paths against the project root).
- **CI (2026-08-19)** — GitHub Actions. Dry-run locally first, then verified
  green on GitHub: run 32264947283, **2m18s**, all steps passing — ruff, 57
  pytest tests in 61s, bronze 5 + 5 rows from the fixtures, `dbt build` 25 nodes,
  and the assertion step reporting `{'resolved': 3, 'unresolved': 2}`.
- **Orchestration (2026-08-19)** — the `lakehouse` DAG, plus the path-resolution
  fix it needed (`resolve_path()`, ADR 0003). The old broken
  `bronze_posts_pipeline.py` is deleted.
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
- **PR #3 is open** from this branch: the dbt layer, housekeeping, the users
  layer and orchestration. It is everything since PR #1.
- Local `main` lags `origin/main`; `git fetch && git checkout main && git pull`
  before branching from it.

## What's left

All five in-scope stages in `ROADMAP.md` are done. What remains is polish, in
rough priority order.

- **More ADRs**: Spark-for-bronze-only, why DuckDB/local-first. (The Spark/dbt
  boundary reasoning is currently only in `AGENTS.md`.)
- **`root_tag` is a dead config knob.** Spark's XML reader ignores `rootTag` on
  read — only `rowTag` selects rows. It is threaded through `pipeline.yaml`,
  both bronze modules and both entrypoints, and does nothing. Removing it
  touches merged code, so it was left alone; worth doing in its own commit.

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
pytest                                           # 65 tests, ~2min
ruff check .                                     # lint
```

Or the whole pipeline as one DAG — setup in `orchestration/AGENTS.md`:

```bash
uv sync --group dbt --group orchestration
airflow dags test lakehouse                      # 12 tasks, ~4min
```

Or reproduce what CI does, on the fixtures — needs no data download:

```bash
DATAFLOW_CONFIG=configs/pipeline.ci.yaml python pipelines/bronze_posts.py
DATAFLOW_CONFIG=configs/pipeline.ci.yaml python pipelines/bronze_users.py
DATAFLOW_DUCKDB_PATH=$PWD/ci.duckdb dbt build --project-dir dbt --profiles-dir dbt \
  --vars "{bronze_posts_path: $PWD/ci-warehouse/bronze.db/posts, \
           bronze_users_path: $PWD/ci-warehouse/bronze.db/users}"
```
