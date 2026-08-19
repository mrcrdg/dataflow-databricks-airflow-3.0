"""The lakehouse DAG: bronze ingestion, then every dbt model as its own task.

    Posts.xml ──[ingest_bronze_posts]──┐
                                       ├──> dbt task group (Cosmos)
    Users.xml ──[ingest_bronze_users]──┘

The two ingestion tasks are independent and run in parallel. Everything after
them is dbt, rendered per model by Cosmos rather than hidden behind a single
`dbt run` — so a failure names the model that failed, and a retry re-runs that
model instead of the whole project.

This replaces `bronze_posts_pipeline.py`, which was written against Airflow 2,
built its own Spark session without the Delta extensions, and imported
`src.dataflow`. It never ran.

## Running it

    uv sync --group dbt --group orchestration
    export AIRFLOW_HOME=...            # anywhere writable
    airflow dags test lakehouse

`dags test` runs the whole DAG in-process, with no scheduler and no webserver.
It needs the real dump in `data/ai.stackexchange.com/` — this DAG is the one
piece of the project that cannot be exercised against the small fixtures.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from airflow.providers.standard.operators.python import PythonOperator
from cosmos import DbtTaskGroup, ExecutionConfig, ExecutionMode, ProfileConfig, ProjectConfig

from airflow import DAG

# This file is orchestration/airflow_dags/lakehouse.py, so the repo root is
# three levels up. Everything Cosmos receives must be absolute: it symlinks the
# dbt project into a temporary directory and runs dbt from there, so a relative
# path would resolve somewhere under /tmp.
REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT_DIR = REPO_ROOT / "dbt"

# Airflow puts the DAGs folder on sys.path, not the repo root, so `pipelines`
# is not importable without this. `dataflow` is, because it is pip-installed;
# `pipelines/` is entrypoints, deliberately not packaged — a job entrypoint is
# not something anything should be able to `import` from site-packages.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _ingest_bronze_posts() -> int:
    # Imported inside the callable, not at module level: the DAG file is parsed
    # by the scheduler on a loop, and importing pyspark there would pay the
    # import cost on every parse for a module only one task needs.
    from pipelines.bronze_posts import main

    return main()


def _ingest_bronze_users() -> int:
    from pipelines.bronze_users import main

    return main()


profile_config = ProfileConfig(
    profile_name="dataflow",
    target_name="dev",
    # Reuse the profiles.yml the CLI uses. Cosmos can generate a profile from an
    # Airflow connection instead, but that would mean two definitions of the
    # same DuckDB target, free to disagree.
    profiles_yml_filepath=DBT_PROJECT_DIR / "profiles.yml",
)

project_config = ProjectConfig(
    dbt_project_path=DBT_PROJECT_DIR,
    # Absolute overrides for the repo-root-relative defaults in dbt_project.yml.
    # Without these, delta_scan() would look for the bronze tables under the
    # temporary directory and find nothing.
    dbt_vars={
        "bronze_posts_path": str(REPO_ROOT / "spark-warehouse" / "bronze.db" / "posts"),
        "bronze_users_path": str(REPO_ROOT / "spark-warehouse" / "bronze.db" / "users"),
    },
    # Same problem, different file: profiles.yml reads this env var so the
    # DuckDB database is the project's, not a throwaway in /tmp that vanishes
    # when the task exits.
    env_vars={"DATAFLOW_DUCKDB_PATH": str(REPO_ROOT / "dataflow.duckdb")},
)

execution_config = ExecutionConfig(
    # LOCAL: run dbt in the same environment as Airflow. Both are installed by
    # `uv sync --group dbt --group orchestration`, so there is nothing to
    # isolate — a virtualenv or container mode would add moving parts for no
    # benefit at this size.
    execution_mode=ExecutionMode.LOCAL,
)

with DAG(
    dag_id="lakehouse",
    # `schedule`, not `schedule_interval` — renamed in Airflow 3.0.
    #
    # None, deliberately: the source is a static archive dump. A daily schedule
    # would re-ingest identical bytes every morning and call it a pipeline.
    # Trigger it when a new dump is downloaded, which is the real cadence.
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["lakehouse", "bronze", "dbt"],
    doc_md=__doc__,
    default_args={
        "owner": "data-platform",
        "retries": 0,
    },
) as dag:
    ingest_bronze_posts = PythonOperator(
        task_id="ingest_bronze_posts",
        python_callable=_ingest_bronze_posts,
    )

    ingest_bronze_users = PythonOperator(
        task_id="ingest_bronze_users",
        python_callable=_ingest_bronze_users,
    )

    transform = DbtTaskGroup(
        group_id="dbt",
        project_config=project_config,
        profile_config=profile_config,
        execution_config=execution_config,
    )

    # Both bronze tables must exist before any dbt model runs: stg_posts reads
    # one, stg_users the other, and marts_posts_users joins them.
    [ingest_bronze_posts, ingest_bronze_users] >> transform
