# configs — pipeline configuration

`pipeline.yaml` is the single source of truth for anything environment-shaped:
source paths, table names, write modes, Spark settings.

## The rule

**If a job needs a value that might differ between environments, it goes here —
not in Python.** Read it with `dataflow.common.config.job_config(layer, job)`.

Override the config file location with the `DATAFLOW_CONFIG` environment
variable. That is how tests point at a small fixture instead of the 191MB dump.

## Structure

Keyed by layer, then job, mirroring `src/dataflow/`:

```yaml
spark:            # session-level settings
bronze:
  posts:          # -> job_config("bronze", "posts")
```

## A warning from this file's own history

It previously read:

```yaml
mode: incremental
source_path: data/raw/posts.csv
```

Every line was false. The path did not exist, the source is XML not CSV, and the
code did `.mode("overwrite")` — the opposite of incremental. Nothing read the
file, so nothing caught it.

**Config that no code reads will drift into fiction.** Keep this file wired to
something that actually executes.
