# Session notes

Running state of the work, so any session (or person) can resume without the
chat history. Update this at the end of a working session. For *why* decisions
were made, see `docs/adr/`; for scope, see `ROADMAP.md`; for a full explanation
aimed at someone reading the project cold, open `docs/lakehouse-report.html`.

_Last updated: 2026-08-19 (second session that day)_

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
| Tests | 65 pytest + 20 dbt, all green. `ruff` clean |
| Docs | `AGENTS.md` per directory, ADRs 0001–0005, `docs/lakehouse-report.html` |

### Git / GitHub state

- **`main` is the truth.** PR #1 and **PR #3 are both merged** (PR #3 merge commit
  `e71d2f7`, 8 commits, 53 files).
- The branch `refactor/local-first-lakehouse` still exists locally and on the
  remote. It is fully merged and safe to delete; left in place deliberately, not
  by oversight.
- Local `main` is up to date with `origin/main` as of this note.

## What's left

**Nothing planned is outstanding.** The four polish items this file used to list
were done on branch `chore/post-merge-polish`:

| Item | Outcome |
|---|---|
| Delete the `root_tag` knob | Gone from both config files, both bronze modules and both entrypoints. A comment at each read site records why the option is absent, so it does not get helpfully re-added. |
| The `pipeline.yaml` pointer to nothing | Replaced: bronze is a full refresh because the source is a static archive, and nothing downstream is incremental. |
| Two more ADRs | `0004-spark-only-at-bronze`, `0005-duckdb-local-first`. Both were prose in `AGENTS.md`; now they are records, cited by the report and the README. |
| README read-through | Fixed a stale test count (said 57, is 65 — 8 skip without the Airflow extras), corrected the claim that `dbt build` needs the full dump when it can run on the fixtures, and linked the two new ADRs. |

Also removed a stale git worktree at `.claude/worktrees/claude-code-otel-observability`,
left over from an unrelated experiment. It was clean and sat on a commit already
in `main`, so nothing was lost; the branch `worktree-claude-code-otel-observability`
still exists.

### Decisions, and what was rejected

- **Kept the branch `refactor/local-first-lakehouse`** rather than deleting it
  now that it is merged. Rejected deleting: it costs nothing and it is the only
  record of the pre-merge shape outside the reflog.
- **Removed the worktree but kept its branch.** Rejected removing both: the
  directory is what nothing exercises; the branch pointer is free.
- **Adding the fixture-based `dbt build` to the README** rather than only to
  `SESSION_NOTES.md`. Rejected leaving it out: the README said the real dump was
  required, which is not true, and that is the exact drift ADR 0002 is about.

### Honest loose ends, none of them blocking

These are gaps by choice, now listed in the report's section 09 rather than
being tracked as work:

- No cloud demonstration — the price of running everywhere for free (ADR 0005).
- The Spark→dbt seam is verified only by CI actually running both.
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
