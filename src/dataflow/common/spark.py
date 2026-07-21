"""Spark session factory.

Single place where a SparkSession is constructed. Jobs never build their own.

If a session already exists — which is the case on Databricks, where the
platform injects one — it is reused as-is. Locally, a session is built with
the Delta Lake extensions wired in.
"""

from __future__ import annotations

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

DEFAULT_APP_NAME = "dataflow"
DEFAULT_WAREHOUSE_DIR = "./spark-warehouse"


def get_spark(
    app_name: str = DEFAULT_APP_NAME,
    warehouse_dir: str = DEFAULT_WAREHOUSE_DIR,
) -> SparkSession:
    """Return an active SparkSession configured for Delta Lake."""
    existing = SparkSession.getActiveSession()
    if existing is not None:
        return existing

    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.warehouse.dir", warehouse_dir)
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()
