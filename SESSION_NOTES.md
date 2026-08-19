# Session notes

Running state of the work, so any session (or person) can resume without the
chat history. Update this at the end of a working session. For *why* decisions
were made, see `docs/adr/`; for scope, see `ROADMAP.md`; for a full explanation
aimed at someone reading the project cold, open `docs/lakehouse-report.html`.

_Last updated: 2026-08-19 (third session that day, closed out)_

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

### Start here next session

**Databricks option A**, if the user agrees to it: upload the two bronze Parquet
exports, create `workspace.bronze.posts` and `workspace.bronze.users`, run
`dbt build --target databricks`, then check the row counts up there against the
baselines. The connection is already verified — `dbt debug --target databricks`
passed on 2026-08-19 against a running 2X-Small serverless warehouse. The
credentials file exists and is filled in.

The user has two unrelated catalogs in that workspace (`standard_lakehouse`,
`data-plataform-jayzern`). Everything this project creates goes in `workspace`.

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

## Decisions, and the alternatives that were rejected

Kept because the reasoning is the part that gets lost. Newest first.

### Databricks

| Decision | Rejected alternative | Why |
|---|---|---|
| Dialect differences go through dispatch macros (`dbt/macros/portable_sql.sql`) | Inline `{% if target.type == 'databricks' %}` branches in each model | The branch would sit in the middle of the SQL a reader is trying to follow. Dispatch keeps the model readable and puts every dialect difference in one file |
| Same, rather than a second dbt project for Databricks | A parallel `dbt-databricks/` project | Two projects means two places to fix a business rule, and they drift. That is the `common/io.py` mistake with more files |
| Double quotes dropped from bronze column names | A quoting macro per adapter | Unquoted identifiers match case-insensitively on **both** engines, so the macro would exist to produce the same string twice |
| Sources left exactly as they were | A per-target sources file | `external_location` sits under `meta:`, which dbt-duckdb reads and other adapters ignore. It already worked; touching it would have been change for its own sake |
| Every `env_var()` in `profiles.yml` carries a default | Bare `env_var('DATABRICKS_HOST')` | dbt renders the whole profiles file on every invocation whatever target is selected, so a bare env_var breaks `dbt build` on a laptop that has never heard of Databricks |
| `dbt-databricks` pinned exactly (`==1.12.4`) | A range (`>=1.12`) | The adapter tracks dbt-core closely and generates SQL; a minor bump can change output. Same reasoning as the Cosmos pin |
| `uv.lock` committed including a `pydantic-core` 2.46.4 -> 2.41.5 downgrade | Leaving the lock untouched | `uv sync` re-locks anyway when pyproject changes, so the downgrade would have happened unrecorded. Committing it made CI the check — and CI passed |
| Credentials live in `~/.dataflow-databricks.env`, mode 600 | A `.env` inside the repo | One `git add -A` away from a published token. Outside the repo it cannot be committed by accident, which is worth more than the convenience |
| Upload bronze as Parquet (option A) is the recommended next step | Moving the XML ingestion to Databricks first (option B) | A is half an hour and tests the claim that matters — the dbt project runs on another warehouse. B is a day, spends compute quota, and nothing depends on doing it first. **Not yet chosen by the user** |

### Visualisation

| Decision | Rejected alternative | Why |
|---|---|---|
| A script that generates a static page | Metabase or Superset | DuckDB allows one writer at a time, so a BI server holding the file open blocks `dbt build`. This is an argument for a warehouse, not against dashboards — the tool belongs on Databricks |
| Same | Evidence | A better fit than Metabase and still on the table (see `ROADMAP.md`), but it is a build step and a framework for a page that is currently one page |
| The script is committed, `viz/out/` is not | Committing the generated page so it renders on GitHub | A committed page is an artifact nothing regenerates (ADR 0002). Offered to the user; the offer stands |
| Hand-authored SVG | A chart library | The page has no runtime dependency at all, which is what lets it open from a filesystem years from now |
| Palette run through a contrast/CVD validator | Picking colours that looked fine | The two series clear ΔE 18.9. Eyeballing is exactly how a chart ends up unreadable for one reader in twelve |
| The ordinal ramp reverses direction in dark mode | Keeping light->dark in both themes | On the dark ground the largest band was the one that disappeared |
| `tests/viz/` asserts structure, not numbers | Asserting the real row counts | The numbers depend on which database is passed in. Structure is what the generator is responsible for |
| An empty gold table raises | Rendering a page of zeroes | The house failure mode: succeeds, looks plausible, means nothing |

### Process

| Decision | Rejected alternative | Why |
|---|---|---|
| One PR per concern (#5 roadmap, #6 Databricks, #7 dashboard, #8 notes) | One "polish" PR | Each is separately reviewable and separately revertable. #6 in particular changes SQL and deserved its own diff |
| `feat/databricks-target` rebased onto `main` | Stacking it on the roadmap branch it was cut from | Stacked PRs make the second diff unreadable until the first merges |
| Merged branches kept on the remote | Deleting them | They cost nothing and they are the only record of the pre-merge shape outside the reflog. Same call as `refactor/local-first-lakehouse` |
| Free Edition facts checked against the docs | Answering from memory | Community Edition was retired on 1 January 2026 and replaced by Free Edition. Getting that wrong would have sent the user to a product that no longer exists |

## Environment note

`uv sync --group dbt --group databricks` was run in this session, so `.venv` now
has the Databricks adapter. **Airflow is not installed** here — it was not before
either, which is why 8 orchestration tests skip locally and run only in CI. To
get them back: `uv sync --group dbt --group orchestration`.

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
