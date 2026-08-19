# configs — pipeline configuration

`pipeline.yaml` is the single source of truth for anything environment-shaped:
source paths, table names, write modes, Spark settings.

## The rule

**If a job needs a value that might differ between environments, it goes here —
not in Python.** Read it with `dataflow.common.config.job_config(layer, job)`.

Override the config file location with the `DATAFLOW_CONFIG` environment
variable. That is how tests and CI point at the small fixtures instead of the
191MB dump.

**Paths here are relative to the repo root, not to the working directory.** They
are resolved by `dataflow.common.config.resolve_path()`, called from the
entrypoints. Resolving against the cwd would work from the CLI and break under
Airflow, which runs from somewhere else — see `docs/adr/0003`.

## Structure

Keyed by layer, then job, mirroring `src/dataflow/`:

```yaml
spark:            # session-level settings
bronze:
  posts:          # -> job_config("bronze", "posts")
```

## The two files

| File | Points at | Used by |
|---|---|---|
| `pipeline.yaml` | the real dump in `data/` | the CLI, the Airflow DAG |
| `pipeline.ci.yaml` | `tests/fixtures/*.xml` | CI, via `DATAFLOW_CONFIG` |

The CI config exists so GitHub Actions can build **real** bronze Delta tables
from the committed fixtures and run the whole dbt project against them. The
alternative — committing a pre-built Delta table — would be a generated artifact
that nothing regenerates, free to drift away from what the ingestion code
actually writes. See `docs/adr/0002`.

It writes to `ci-warehouse/`, never `spark-warehouse/`, so reproducing a CI
failure locally cannot clobber real bronze tables. Both properties are asserted
in `tests/common/test_config.py`.

## A warning from this file's own history

It previously read:

```yaml
mode: incremental
source_path: data/raw/posts.csv
```

Every line was false. The path did not exist, the source is XML not CSV, and the
code did `.mode("overwrite")` — the opposite of incremental. Nothing read the
file, so nothing caught it.

**Config that no code reads will drift into fiction.** Keep both files wired to
something that actually executes — `pipeline.yaml` to the jobs, `pipeline.ci.yaml`
to CI, and both to tests that assert they parse and name files that exist.
