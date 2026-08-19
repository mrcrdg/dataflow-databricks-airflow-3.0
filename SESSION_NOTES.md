# Session notes

Running state of the work, so any session (or person) can resume without the
chat history. Update this at the end of a working session. For *why* decisions
were made, see `docs/adr/`; for scope, see `ROADMAP.md`; for a full explanation
aimed at someone reading the project cold, open `docs/lakehouse-report.html`.

_Last updated: 2026-08-19 (third session that day)_

## Where things are

**All seven planned stages are complete and merged to `main`.** The project is a
working, tested, orchestrated, local-first lakehouse that anyone can clone and
run: **bronze (Spark/Delta) → silver + gold (dbt/DuckDB) → scheduled by Airflow,
checked by CI.**

### Done and verified

| Piece | State |
|---|---|
| `bronze.posts` | `python pipelines/bronze_posts.py` — 26,764 rows |
| `bronze.users` | `python pipelines/bronze_users.py` — 71,811 rows |
| `stg_posts`, `stg_users` | dbt views over the Delta tables, read in place via `delta_scan` |
| `marts_top_tags` | gold table, top-N tags (N = `top_tags_limit`, default 100) |
| `marts_posts_users` | gold table, one row per post + author — 26,764 rows |
| Orchestration | `lakehouse` DAG, Airflow 3.2 + Cosmos 1.15.1, 12 tasks, verified 12/12 in 240s |
| CI | `.github/workflows/ci.yml` — ruff, pytest, then the whole dbt project built from fixtures. 2m18s, green |
| Tests | 72 pytest + 20 dbt, all green. `ruff` clean (8 pytest skip without the Airflow extras) |
| Docs | `AGENTS.md` per directory, ADRs 0001–0005, `docs/lakehouse-report.html`, `docs/databricks.md` |
| Dashboard | `python viz/build_dashboard.py` — charts from the gold tables, output gitignored |
| Databricks | models are dialect-portable and the target exists; **never run against a workspace** |

### Git / GitHub state

- **`main` is the truth.** PR #1 and **PR #3 are both merged** (PR #3 merge commit
  `e71d2f7`, 8 commits, 53 files).
- The branch `refactor/local-first-lakehouse` still exists locally and on the
  remote. It is fully merged and safe to delete; left in place deliberately, not
  by oversight.
- Local `main` is up to date with `origin/main` as of this note.

## What's left

Nothing is blocking. `ROADMAP.md` now carries the five candidates for next work
with their real costs; the two that have been started are below.

### Databricks — half done (PR #6)

The models no longer contain DuckDB-only SQL, and `dbt/profiles.yml` has a
`databricks` target reading every credential from the environment. **It has
never been run against a real workspace**, so treat it as untested code, not a
working feature.

What is left: an account (Free Edition), bronze tables in the workspace, then
`dbt build --target databricks`. Steps and credentials in `docs/databricks.md`.

The finding worth remembering: ADR 0005's "adapter swap, not a rewrite" was an
assumption. Three functions differed, and the models quoted bronze columns as
`p."Id"` — which **Databricks reads as a string literal**, so every one would
have returned the text `Id` instead of the column. Rows, no error. Fixed in
`dbt/macros/portable_sql.sql` and by dropping the quotes.

### Visualisation — first cut done (PR #7)

`viz/build_dashboard.py` queries the gold tables and writes a self-contained
page. `viz/out/` is gitignored — the script regenerates it. `tests/viz/` is what
exercises it, and it caught two bugs on the first run: a crash on any database
with an empty score band, and an empty gold table rendering as zeroes rather
than failing.

Published copy: <https://claude.ai/code/artifact/d522d0db-0984-4c06-9b1e-ffcb0fbd2e21>

A real BI tool (Metabase, Superset) was considered and deferred: DuckDB allows
one writer at a time, so a BI server holding the file open blocks `dbt build`.
That is an argument for a warehouse, not against dashboards.

### Honest loose ends, none of them blocking

- CI cannot test the Databricks target — that would need a workspace and a token
  in repo secrets. It is verified by running it, and nothing else.
- No cloud demonstration yet (ADR 0005).
- Nothing is incremental; every run rebuilds every layer.
- The README is checked by human attention only, unlike the report.

## Deliberately shelved (see ROADMAP.md for the reasoning)

- **Databricks** as production target — dbt makes it an adapter swap.
- **LLM enrichment layer** — needs determinism, caching, a cost ceiling and an
  accuracy eval to be worth doing; that is a project in itself.
- **Dockerfile** — deleted, not fixed. Returns only with a CI job that builds it.
  CI now exists, so that precondition is met.
- **Streaming, Kubernetes** — the source is a static archive; both would be
  theatre.

## How to run everything

```bash
uv sync --group dbt                              # deps (add --group orchestration for Airflow)
uv pip install -e . --no-deps                    # make `dataflow` importable
python pipelines/bronze_posts.py                 # bronze: Posts.xml -> Delta (26,764 rows)
python pipelines/bronze_users.py                 # bronze: Users.xml -> Delta (71,811 rows)
dbt build --project-dir dbt --profiles-dir dbt   # silver + gold + 20 dbt tests
python viz/build_dashboard.py                    # charts -> viz/out/ (gitignored)
pytest                                           # 72 tests, ~2min
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

## Traps worth knowing before you touch anything

Each of these fails **silently** — right row counts, no exception, wrong data.

1. **Spark's XML reader ignores `rootTag` on read.** Only `rowTag` selects rows,
   and a wrong `rowTag` returns an empty DataFrame rather than raising: the job
   writes zero rows and reports success. The `rootTag` option is no longer set
   anywhere — that is deliberate, not an omission; a comment at each read site
   says so.
2. **`collect()` converts timestamps to the host's local timezone**, even though
   the session timezone is pinned to UTC (ADR 0001). Assert on timestamps by
   formatting *inside Spark* (`date_format`), never on a Python `datetime` from
   `collect()` — otherwise the test passes or fails depending on who runs it.
3. **The grain invariant:** `marts_posts_users` must be exactly 26,764 rows, the
   same as `bronze.posts`. Any other number means `stg_users.user_id` gained a
   duplicate and the LEFT JOIN fanned out.
4. **Cosmos runs dbt from a temporary directory.** A relative DuckDB path there
   creates a throwaway database deleted on task exit — the DAG goes green and
   writes nothing. Absolute paths come from `dbt_vars` / `env_vars` in the DAG,
   and from `config.resolve_path()` for the Python jobs (ADR 0003).
5. **`astral-sh/setup-uv` publishes no moving major tag after v7.** `@v10` does
   not resolve; pin the exact version. GitHub's own actions still do publish
   moving majors.
6. **Databricks SQL reads `"Id"` as the string `Id`**, not as a column. The
   models used to quote every bronze column that way. It would have returned
   rows full of constants — no error, right count, wrong data. Unquoted names
   match case-insensitively on both engines, which is why the quotes are gone.
7. **A `dbt build` or a dashboard against an empty database succeeds.** Both now
   refuse: CI asserts row counts after the build, and the dashboard generator
   raises rather than drawing a page of zeroes.

## Conventions this project holds to

- **Never ask a yes/no question without first stating the trade-off** — what
  changed, what it means, the consequence of each option, and a recommendation.
  Full format in `AGENTS.md` under "Decision points".
- **Stage git changes explicitly. Never `git add -A`** — it has caused stray-file
  commits here twice.
- **An artifact must be exercised by something automated, or be deleted**
  (ADR 0002). This applies to docs too: `tests/docs/` asserts the report's
  structural claims against the repo.
- Comment code so a human reads it easily; keep a directory-level `AGENTS.md`
  per key folder.
