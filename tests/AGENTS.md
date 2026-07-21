# tests

```bash
pytest              # full suite, ~60s (most of it is Spark starting up)
pytest tests/common # fast, no Spark
```

## Structure

```
conftest.py            session-scoped Spark fixture + fixture paths
fixtures/              5 real rows from Posts.xml (3.5KB)
bronze/test_posts.py   ingestion: schema, transforms, Delta round-trip
common/test_config.py  config loading, no Spark
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

## Known baseline

Bronze ingestion of the full dump produces **26,764 rows**. The suite does not
assert this (it uses the fixture), but any refactor should be checked against it:

```bash
python pipelines/bronze_posts.py
```
