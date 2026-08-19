# Roadmap

Scope decisions for this project, including what was deliberately left out.
Rationale for each choice lives in `docs/adr/`.

## Target architecture

```
Posts.xml ──┐
            ├─[Spark]──> bronze (Delta) ──[dbt]──> silver ──[dbt]──> gold
Users.xml ──┘                                       |
                                              [Airflow + Cosmos]
```

Spark handles ingestion only — parsing XML is the one job dbt cannot do.
Everything downstream is SQL, so it belongs in dbt.

## In scope

| # | Stage | Status |
|---|-------|--------|
| 1 | Repo hygiene — packaging, `uv`, `.gitignore` | done |
| 2 | Single entrypoint + real `common/` (Spark factory, config loader) | done |
| 3 | Tests for the bronze layer | done |
| 4 | dbt-duckdb: silver + gold ported from notebooks, with dbt tests | done — `stg_posts`, `stg_users`, `marts_top_tags`, `marts_posts_users` |
| 5 | Airflow 3 + Cosmos orchestration | done — `lakehouse` DAG, 12 tasks, verified end to end |
| 6 | Docs: README, ADRs, `CLAUDE.md`, "How I used AI" | done — ADRs 0001–0005, per-directory `AGENTS.md`, and `docs/lakehouse-report.html` |
| 7 | CI: lint, tests and the full dbt DAG on every push | done — builds bronze from the fixtures, ~2m18s, no generated artifact committed |

Current state, and what is being worked on next, is tracked in `SESSION_NOTES.md`.

## Deliberately out of scope

These were considered and deferred. They are not oversights.

### Databricks as production target

Recorded as `docs/adr/0005-duckdb-local-first.md`.

The pipeline was originally prototyped on Databricks (see `notebooks/`), but the
runnable version targets **DuckDB locally**.

**Why:** a portfolio project that requires cloud credentials is a project nobody
can run. Local-first means `git clone` → working pipeline in minutes, and CI can
run the full suite on every push at zero cost.

dbt makes this a swap of adapter, not a rewrite — `dbt-duckdb` locally,
`dbt-databricks` in the cloud, same models. Databricks returns when there is a
reason to pay for it.

### LLM enrichment layer

An enrichment step between silver and gold — classifying post topics with an
LLM — is a natural fit for this dataset, and the existing tags provide free
ground truth for evaluation.

**Why deferred:** doing it properly means solving determinism (LLM output varies
between runs, dbt tests expect stability), caching keyed by content hash so
re-runs are free, a hard cost ceiling, and an accuracy eval against a
hand-labelled sample. That is a project in itself. A version without those
properties would be worse than not building it at all.

Planned shape when picked up: a separate materialized `enrichment` layer,
computed once outside dbt, exposed to dbt as a source — keeping the dbt DAG
fully deterministic.

### Containerisation

There was a `Dockerfile`. It was deleted, not fixed, because it did not work and
nothing in the repo would have told you so:

- it installed `pyspark` and `delta-spark` unpinned, on top of a base image that
  already contained PySpark 3.5.0, ignoring `pyproject.toml` and `uv.lock`
- it never installed `pyyaml`, so every pipeline died on `import yaml`
- `PYTHONPATH=/app` was wrong for a `src/` layout — `import dataflow` failed

No CI built the image, so none of that surfaced. **A container that ships broken
is worse than no container**: it invites someone to trust it.

When this comes back it should arrive with a CI job that builds the image and
runs the pipeline inside it. Until something exercises it, it will drift — the
same way `pipeline.yaml` drifted into describing a CSV that never existed.

CI now exists (`.github/workflows/ci.yml`), so the precondition is met: adding a
Dockerfile means adding a job that builds it and runs a pipeline inside it.

### Not planned

- **Streaming** — the source is a static XML dump. Streaming would be theatre.
- **Kubernetes** — the original README claimed portability across Databricks,
  Airflow and Kubernetes. Committing to one target and doing it well beats
  abstracting over three hypothetical ones.
- **BI / dashboard layer** — gold tables are the deliverable.
