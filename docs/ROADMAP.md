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

## Candidate next work

All seven planned stages are done, so nothing below is outstanding — these are
the options for a *next* piece of work, with what each one actually costs. They
are listed in the order they are worth doing, not in the order they were thought
of.

### 1. A container, plus a CI job that builds it

**Size:** small, with a clear finish line.

The `Dockerfile` was deleted rather than fixed (see below), and the condition for
its return was a CI job that builds the image and runs a pipeline inside it. CI
now exists, so that condition is met. This is the only candidate that closes a
gap the repo has already written down against itself.

**Done means:** `docker build` in CI, then `python pipelines/bronze_posts.py`
inside the container against the fixtures, with the row count asserted. If the
job cannot be made to pass, the Dockerfile is deleted again — that is the rule.

### 2. The LLM enrichment layer

**Size:** a project in itself. Days, not hours.

Classify post topics with a language model, between silver and gold. The
existing tags are free ground truth to score against, which is what makes this
worth doing rather than a demo.

**The four things that make it real**, and without which it should not be built:
determinism (dbt tests expect stable output; model calls are not stable),
caching keyed by a content hash so re-runs cost nothing, a hard cost ceiling, and
an accuracy evaluation against a hand-labelled sample.

**Planned shape:** a separate materialised `enrichment` layer, computed once
outside dbt and exposed to dbt as a source, so the dbt DAG stays deterministic.

### 3. A visualisation layer

**Size:** small to medium, depending on the tool. Reopened — this was previously
listed as not planned.

The gold tables answer questions but nothing displays the answers. See
"Visualisation" below for the options and what each one costs.

### 4. Incremental models

**Size:** small, but solves a problem this project does not have.

Every run rebuilds every layer from the raw archive. That is correct and fast at
this size, and the source is a static archive that never changes — so this would
be learning the pattern rather than fixing anything. Worth doing *as an
exercise*, worth being honest that that is what it is.

### 5. Databricks, for real

**Size:** small in code, permanent in consequence.

The adapter swap is genuinely small — `dbt-databricks` for `dbt-duckdb`, same
models, and Spark sessions already come from one factory. The cost is an account
and a bill, and it undoes the "anyone can clone and run this" property the whole
project is built on (ADR 0005). It stays deferred until someone actually asks to
see it.

## Visualisation

Previously listed under "not planned" on the grounds that the gold tables are the
deliverable. **Reopened**, because a lakehouse nobody can look at is a hard thing
to show anyone.

The constraint that decides this is the same one as everywhere else in the
project: **an artifact must be exercised by something automated, or it will drift**
(ADR 0002). That rules out anything whose correctness depends on a human opening
it and looking.

| Option | What it is | Fits? |
|---|---|---|
| **Evidence** | Markdown + SQL files that build to a static site, reads DuckDB directly | Best fit — CI can build it on every change, so a broken query fails the build |
| **Streamlit / Marimo** | A Python app serving charts from the DuckDB file | Works, but needs a running server; CI can only check that it imports |
| **Metabase / Superset** | A full BI server, browsed in a browser | Heaviest. Needs a container and a database of its own; the tool becomes the project |
| **Databricks dashboards** | AI/BI dashboards over tables in a Databricks workspace | Possible without a bill — Free Edition (which replaced Community Edition on 1 Jan 2026) includes AI/BI dashboards and a serverless SQL warehouse. Still needs an account and the gold tables pushed to a workspace, so it is a *second* home for the data, not the local one |
| **A generated HTML report** | One page of charts, produced by a script from the gold tables | Cheapest. Same shape as `docs/lakehouse-report.html`, which tests already check |

A first cut of the generated page exists as a prototype, built from the real
gold tables and published at
<https://claude.ai/code/artifact/d522d0db-0984-4c06-9b1e-ffcb0fbd2e21>. It is
**not in the repo**: by ADR 0002 it only earns a place here alongside a test that
runs the generator against the CI fixtures, so a broken query fails the build
rather than producing a quietly wrong chart.

**Recommendation:** the generated HTML page first — it costs an afternoon,
requires no new service, and can be regenerated in CI so it cannot go stale.
Evidence if a browsable multi-page site is wanted later.

Databricks dashboards are a genuine option now that Free Edition exists, but
they answer a different question: *what would this look like on the platform?*
rather than *what do the tables say?* Doing them means running the dbt project
against `dbt-databricks` first, which is candidate 5 — so they follow that
decision rather than replacing it.

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
- ~~**BI / dashboard layer**~~ — was "gold tables are the deliverable". Reopened
  on 2026-08-19; see "Visualisation" above.
