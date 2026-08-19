# pipelines — execution layer

Entrypoints. One file per job, each exposing a `main()`.

## What belongs here

Wiring, and only wiring:

1. Read config for the job
2. Get a Spark session from `dataflow.common.spark.get_spark()`
3. Call the transformation in `src/dataflow/`
4. Log the outcome

## What does not belong here

Transformation logic. If you are writing a `select`, a `join`, or a schema in
this directory, it is in the wrong place — it goes in `src/dataflow/`.

## Why `main()` and not a script body

```python
def main() -> int: ...

if __name__ == "__main__":
    main()
```

The same `main()` is callable three ways without modification: from the CLI, from
an Airflow `PythonOperator`, and from a Databricks job. A bare script body only
works from the CLI. This is the whole reason the execution layer is separate from
the logic layer.

## History — why this directory looked broken

Bronze posts once had **three** entrypoints: `run_bronze_posts.py` at the repo
root (the only one that worked), `pipelines/bronze_posts.py` (never called by
anything), and the Airflow DAG (misconfigured). They have been collapsed into
one. If you find yourself adding a second way to run an existing job, stop.

## Running

```bash
python pipelines/bronze_posts.py
python pipelines/bronze_users.py
```

Requires `uv pip install -e . --no-deps` so `dataflow` is importable.

There is no silver or gold entrypoint here, and there should not be: those
layers are dbt models, run with `dbt build`. One way to run each job.
