# 1. Pin the Spark session timezone to UTC

- **Status:** accepted
- **Date:** 2026-07-21

## Context

The Stack Exchange dump stores timestamps without a timezone offset:

```xml
<row Id="1" CreationDate="2016-08-02T15:39:14.947" ... />
```

These values are UTC — that is the dump's documented convention — but nothing in
the file says so.

Spark's `spark.sql.session.timeZone` defaults to the JVM's timezone, which is
whatever the host machine is configured to. On the machine where bronze was
first run that was `Europe/Helsinki` (UTC+3), so Spark interpreted the naive
string as local time and stored the instant three hours earlier than intended:

```
source:  2016-08-02T15:39:14.947        (UTC)
stored:  2016-08-02T15:39:14.947+03:00  (= 12:39:14 UTC)
```

Every timestamp column in bronze was affected — 6 columns across 26,764 rows.

The bug was invisible in normal use. Row counts were correct, no job failed, and
`Posts.xml` looked fine next to the table. It surfaced only when reading the
Delta table from DuckDB, where the offset became explicit.

## Decision

Set `spark.sql.session.timeZone = UTC` in `dataflow.common.spark.get_spark()`,
for both newly-built sessions and any pre-existing session that is reused (the
Databricks path).

Pin it with a test: `tests/common/test_spark.py::test_session_timezone_is_utc`.

## Consequences

**Positive**

- Timestamps in bronze now match the source exactly.
- Ingestion is reproducible: the same `Posts.xml` produces identical output on
  any machine, in any timezone. This matters more than the correctness fix —
  the project's stated goal is that anyone who clones it can run it, and output
  that varies by host timezone breaks that.
- Silver and gold are built after this fix, so no downstream model inherits the
  shift.

**Negative**

- Re-running bronze rewrites the table; timestamps move by the host's UTC offset
  relative to the previous version. Any analysis run against the old table is
  invalidated. Row count is unchanged at 26,764.
- Timestamps are now stored in UTC regardless of the reader's locale. Anything
  wanting local-time display must convert explicitly, downstream.

## Notes

The general rule this follows: **store in UTC, convert at the edges**. Config
that depends on the host environment is a reproducibility bug waiting to happen,
and the ones that do not crash are the expensive kind.
