# 4. Spark only at bronze; everything downstream is dbt

- **Status:** accepted
- **Date:** 2026-08-19

## Context

The project started as a set of Databricks notebooks that did every layer in
PySpark: read the XML, clean it, aggregate it, write the results. Porting that
shape into a repo would have meant a `silver/` and a `gold/` package alongside
`bronze/`, each holding DataFrame code.

Two things made that the wrong move.

The first is what the layers actually do. Bronze parses XML — a format Spark
reads and SQL cannot. Silver and gold rename columns, cast types, filter, join
and aggregate. That is SQL, written in Python only because the notebook happened
to be Python.

The second is what a hand-rolled transformation layer has to grow before it is
trustworthy: a way to declare that `stg_users.user_id` is unique, a record of
which table feeds which, generated documentation, incremental logic that does
not silently double-count, and a way to run one model without running the whole
chain. dbt has all of that. Writing it again in PySpark would be rebuilding dbt,
worse, in project time that buys nothing.

There is a real cost on the other side: two engines in one pipeline, two sets of
dependencies, and a boundary where a Delta table written by Spark is read by
DuckDB. That boundary is where the `delta_scan` path bugs live (ADR 0003).

## Decision

**Spark handles ingestion. dbt handles every transformation after it.**

- `src/dataflow/bronze/` is the only place PySpark appears in production code.
  It reads XML, strips the reader's attribute prefix, and writes Delta. No
  business logic — bronze is a faithful typed copy of the source.
- Silver and gold are dbt models over those Delta tables, read in place with
  DuckDB's `delta_scan`. There is no Spark job that writes silver or gold, and
  adding one would be a bug, not a feature.
- The two empty `silver/` and `gold/` Python packages left over from the port
  were deleted rather than kept as placeholders (`ea3f050`), because a stub
  invites someone to fill it.

The test for where a piece of work belongs: **can dbt do it?** If the input is
already a table, the answer is yes, and Spark stays out of it.

## Consequences

**Positive**

- Tests, lineage, docs and model-level selection come free with dbt instead of
  being rebuilt. The 20 dbt tests in this project are configuration, not code.
- Each layer is testable in the way that suits it: bronze transformations are
  pure `DataFrame -> DataFrame` functions with pytest around them; silver and
  gold are SQL with dbt tests around them.
- Swapping the warehouse is an adapter change, not a rewrite — which is what
  makes the local-first decision affordable (ADR 0005).

**Negative**

- Two engines, so two dependency groups and two failure vocabularies. A
  contributor has to know a little of both.
- The handoff is a file path, not an API. Spark writes a Delta directory, dbt
  reads it by path, and nothing type-checks across that seam. It is exercised by
  CI, which builds bronze from fixtures and then runs the whole dbt project
  against what Spark actually wrote.
- Spark is heavier than this dataset needs. That is accepted deliberately: the
  ingestion patterns are the point of the project, and `AGENTS.md` says so
  rather than pretending 191MB is big.

## Notes

The general form: **use the tool that owns the problem, and stop where it stops
owning it.** Spark owns "turn this file into a table". dbt owns "turn this table
into another table". Neither is improved by doing the other's job.
