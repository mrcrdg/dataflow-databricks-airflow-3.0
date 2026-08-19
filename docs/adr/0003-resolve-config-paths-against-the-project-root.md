# 3. Resolve config paths against the project root, not the working directory

- **Status:** accepted
- **Date:** 2026-08-19

## Context

`configs/pipeline.yaml` declares paths relative to the repo root:

```yaml
source_path: data/ai.stackexchange.com/Posts.xml
warehouse_dir: ./spark-warehouse
```

Nothing resolved them, so they were passed to Spark as-is and interpreted
against the **current working directory**. That works for the documented way to
run a job — `python pipelines/bronze_posts.py` from the repo root — and only for
that way.

Adding the Airflow DAG broke the assumption in two places at once:

- Airflow runs task callables from its own directory, not the repo root, so
  `data/ai.stackexchange.com/Posts.xml` did not exist from there.
- Cosmos symlinks the dbt project into a temporary directory and runs dbt from
  there, so `delta_scan('spark-warehouse/bronze.db/posts')` found nothing and
  `path: dataflow.duckdb` created a database under `/tmp` that was deleted when
  the task exited.

The second one is the dangerous shape: dbt would run every model against an
empty throwaway database, write its tables into it, report success, and leave
no trace. Green DAG, no data.

## Decision

Paths in `pipeline.yaml` stay relative — that is the readable form, and the form
a reader can check against `ls`. They are resolved at the point of use, against
the **project root**, defined as the directory containing `configs/`:

- `dataflow.common.config.resolve_path()` does this for the Python jobs, called
  from the entrypoints in `pipelines/` (resolution is wiring, so it belongs in
  the execution layer, not in the transformation modules).
- The DAG passes absolute paths to Cosmos explicitly, via `dbt_vars` for the
  Delta tables and `env_vars` for the DuckDB file. `dbt/profiles.yml` reads
  `env_var('DATAFLOW_DUCKDB_PATH', 'dataflow.duckdb')`, so the bare CLI keeps
  working with no environment set up.

An absolute path in the config is passed through unchanged — the escape hatch
for a deployment whose data lives outside the repo.

## Consequences

**Positive**

- A job produces the same result from any working directory. That is what makes
  "the same `main()` runs from the CLI, from Airflow, and from Databricks" a
  true statement rather than an aspiration.
- The failure mode above is now pinned by tests at both ends:
  `test_resolve_path_does_not_depend_on_the_working_directory` and
  `test_every_dbt_task_gets_absolute_paths`.

**Negative**

- There are now two mechanisms — a Python helper and dbt's `env_var` — doing the
  same job for the same reason. They cannot be unified: dbt does not import our
  Python. The duplication is documented in `orchestration/AGENTS.md` so it reads
  as a constraint rather than an oversight.
- `resolve_path()` locates the project root by walking up to `configs/`. A
  checkout that moved or renamed that directory would resolve to the wrong
  place; `config_path()` already had this dependency, so it is not new, but it
  is now load-bearing for more things.

## Notes

The general form is the same one as ADR 0001: **behaviour that depends on
ambient machine state — the host timezone there, the working directory here —
is behaviour that changes depending on who runs it.** Pin it, or it is not
reproducible.
