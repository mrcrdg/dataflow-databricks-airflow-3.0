"""Entrypoint for the bronze posts job.

This is the execution layer: it builds a Spark session, reads config, and calls
the transformation module. It holds no business logic, so the same `main()` can
be invoked from the CLI, from Airflow, or from a Databricks job.

    python pipelines/bronze_posts.py
"""

from __future__ import annotations

from dataflow.bronze import posts
from dataflow.common.config import job_config, resolve_path, spark_config
from dataflow.common.logging import get_logger
from dataflow.common.spark import get_spark

logger = get_logger("pipelines.bronze_posts")


def main() -> int:
    """Run the bronze posts ingestion. Returns rows written."""
    cfg = job_config("bronze", "posts")
    spark_cfg = spark_config()

    # Resolved against the project root, not the current directory: this same
    # main() is called from the CLI and from an Airflow task, and Airflow does
    # not run from the repo root.
    spark = get_spark(
        app_name=spark_cfg.get("app_name", "dataflow"),
        warehouse_dir=resolve_path(spark_cfg.get("warehouse_dir", "./spark-warehouse")),
    )

    database = cfg["table"].split(".")[0]
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {database}")

    row_count = posts.run(
        spark,
        source_path=resolve_path(cfg["source_path"]),
        table=cfg["table"],
        root_tag=cfg.get("root_tag", "posts"),
        row_tag=cfg.get("row_tag", "row"),
        write_mode=cfg.get("write_mode", "overwrite"),
    )

    logger.info("Job finished: %s rows in %s", row_count, cfg["table"])
    return row_count


if __name__ == "__main__":
    main()
