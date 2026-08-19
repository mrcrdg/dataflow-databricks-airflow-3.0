# tests

```bash
pytest                    # full suite, ~2min (most of it is Spark starting up)
pytest tests/common       # fast, no Spark
pytest tests/orchestration # DAG integrity, ~20s, needs the orchestration extras
```

## Structure

```
conftest.py             session-scoped Spark fixture + fixture paths
fixtures/               5 real rows each from Posts.xml and Users.xml
bronze/test_posts.py    ingestion: schema, transforms, Delta round-trip
bronze/test_users.py    same, plus null-vs-blank and the UTC storage check
common/test_config.py   config loading and path resolution, no Spark
orchestration/          DAG parses, Cosmos renders, graph is the intended shape
```

## Two kinds of test, kept apart

**Pure transformation tests** — no I/O. They build a small DataFrame in memory
and assert on the result. Fast, and they pin down behaviour precisely.

**Ingestion tests** — read the fixture file, exercise reader and writer.

The split is diagnostic: if the pure tests fail, the *logic* is wrong; if only
the ingestion tests fail, the *plumbing* is wrong.

## Why the fixture is real data, not synthetic

`fixtures/posts_sample.xml` is the first 5 rows of the actual dump. Real rows
carry the awkward parts a hand-written fixture would tidy away — HTML-escaped
bodies, `|pipe|delimited|` tags, and answers with no Title or Tags at all.

It is 3.5KB, so tests never touch the 191MB source file and the suite runs
anywhere, including CI with no data downloaded.

## Why the Spark fixture is session-scoped

Starting a SparkSession costs several seconds. Per-test sessions would make the
suite slow enough that nobody runs it, and **a suite nobody runs is worth
nothing**. It writes to a temp warehouse so tests never dirty
`./spark-warehouse`.

## Properties worth protecting

Some tests guard behaviour the current data does not exercise, which is exactly
why they are written down:

- `test_clean_columns_only_strips_leading_underscores` — the original code used
  `replace("_", "")`, which would mangle `user_id` into `userid`. No source
  column has an internal underscore *today*.
- `test_run_is_idempotent` — re-running must not duplicate rows. A pipeline that
  doubles its data on retry is worse than one that fails.
- `test_real_config_is_valid_and_complete` — asserts the committed
  `configs/pipeline.yaml` actually works. This is the test that would have caught
  the old config pointing at a CSV that never existed.
- `test_resolve_path_does_not_depend_on_the_working_directory` — jobs are
  launched from the CLI at the repo root *and* from Airflow, which is elsewhere.
  A cwd-relative path works in the first case and fails in the second, so the
  CLI would keep passing while the DAG broke.
- `test_timestamps_are_stored_as_utc` — asserts the stored instant by formatting
  it *inside Spark*. `collect()` converts to the host's local timezone, so the
  obvious version of this test passes or fails depending on who runs it — the
  exact bug ADR 0001 exists to prevent.
- `test_every_dbt_task_gets_absolute_paths` — Cosmos runs dbt from a temp
  directory; a relative DuckDB path there produces a run that reports success
  and writes nothing.

## Known baselines

The suite runs on fixtures, so it does not assert these. Any refactor should be
checked against them — the table is in the root `AGENTS.md`:

```bash
python pipelines/bronze_posts.py    # 26,764 rows
python pipelines/bronze_users.py    # 71,811 rows
```
