# orchestration — scheduling

How jobs get triggered. No logic, no wiring — those live in `src/dataflow/` and
`pipelines/`. A DAG task should be a thin call to a `pipelines/*.main()`.

## Status: not yet working

`airflow_dags/bronze_posts_pipeline.py` is the original sketch and does **not**
run. Known problems:

1. Uses `schedule_interval=`, **removed in Airflow 3.0**. The parameter is now
   `schedule=`. The installed version is Airflow 3.2.0.
2. Builds its own SparkSession without the Delta extensions, so writes fail.
   It must use `dataflow.common.spark.get_spark()`.
3. Imports `src.dataflow...`, which predates the package layout. Correct import
   is `dataflow...`.

This is scheduled work, not an oversight — see `ROADMAP.md`.

## Intended design

**Airflow 3 + [Cosmos](https://www.astronomer.io/docs/learn/airflow-dbt/).**

Cosmos renders each dbt model as its own Airflow task rather than hiding the
whole project behind a single `dbt run` command. That means per-model retries,
per-model timing, and the dbt lineage graph visible in the Airflow UI. When
model 7 of 12 fails you retry model 7, not everything.

Planned DAG shape:

```
ingest_bronze_posts  (PythonOperator -> pipelines.bronze_posts.main)
        |
   dbt model tasks   (rendered by Cosmos from the dbt project)
```

## databricks_jobs/

Empty, and deliberately so. Databricks is the documented production target but
is out of scope for now.
