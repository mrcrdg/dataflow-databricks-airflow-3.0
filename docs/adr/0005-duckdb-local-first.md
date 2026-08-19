# 5. DuckDB locally as the runtime target, not Databricks

- **Status:** accepted
- **Date:** 2026-08-19

## Context

The original prototype ran on Databricks: the notebooks in `notebooks/` are that
version, and the repository name still carries it. Keeping Databricks as the
runtime target meant every one of these was required before anyone could see the
project run: a workspace, a cluster, credentials, and a bill.

For a project whose purpose is to be read and run by other people — a reviewer,
a future employer, a contributor, CI — that is a hard stop. The most likely
outcome for a cloud-only pipeline is that nobody ever executes it, and an
unexecuted pipeline drifts into the same fiction as the config naming a CSV that
never existed (ADR 0002).

The counter-argument is honest and was weighed: Databricks is what the job
market asks about, and a local DuckDB build does not demonstrate cluster
operation, Unity Catalog, or job scheduling on a managed platform.

## Decision

**The runtime target is DuckDB, running locally. Databricks is documented as the
production target and is deliberately out of scope.**

- `dbt/profiles.yml` uses `dbt-duckdb`, reading the Spark-written Delta tables in
  place via `delta_scan`.
- Everything runs from a clone: `uv sync`, two Python entrypoints, `dbt build`.
  No account, no credentials, no cost.
- CI runs the *whole* project — bronze ingestion from committed XML fixtures,
  then every dbt model and test — on every pull request, at zero cost. That is
  only possible because the target is local.
- The notebooks stay as frozen prototypes, with a port-status table in
  `notebooks/AGENTS.md`. They are history, not a second implementation.

This is affordable because of ADR 0004: with the transformations in dbt,
Databricks is an adapter swap — `dbt-databricks` in place of `dbt-duckdb`,
same models — plus a Spark session that already comes from one factory
(`dataflow.common.spark.get_spark`). It is not a rewrite waiting to happen.

## Consequences

**Positive**

- `git clone` to a working lakehouse in minutes, which is the difference between
  a project people run and a project people take on trust.
- CI can afford to be thorough. The full dbt DAG on every pull request would be
  a metered cluster spin-up against a cloud warehouse.
- The pipeline is fast enough to iterate on: the dbt build over the fixtures
  finishes in under three seconds.

**Negative**

- The project does not demonstrate cloud operation — no cluster sizing, no
  workspace configuration, no managed scheduling. Anyone evaluating it for that
  will not find it here.
- DuckDB and Databricks SQL are not identical. A model that builds locally can
  still fail on Databricks, and nothing in this repo would catch that until
  someone runs it there.
- Delta support in DuckDB is an extension read path. It reads what Spark wrote;
  it does not write Delta, which is part of why bronze stays in Spark.

**What would reverse this**

A concrete reason to pay for it — a dataset that genuinely does not fit on one
machine, or a deployment someone actually needs. Until then, `ROADMAP.md` keeps
Databricks listed as deferred with this reasoning, so it reads as scope control
rather than an omission.

## Notes

The general form, shared with ADR 0002: **an artifact nobody can exercise will
not stay true.** A cloud-only pipeline is exercised by nothing but its author's
memory.
