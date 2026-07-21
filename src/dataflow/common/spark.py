"""Spark session factory.

Single place where a SparkSession is constructed. Jobs never build their own.

If a session already exists — which is the case on Databricks, where the
platform injects one — it is reused as-is. Locally, a session is built with
the Delta Lake extensions wired in.
"""

from __future__ import annotations

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

from dataflow.common.logging import get_logger

logger = get_logger("dataflow.common.spark")

DEFAULT_APP_NAME = "dataflow"
DEFAULT_WAREHOUSE_DIR = "./spark-warehouse"

# The Stack Exchange dump stores naive timestamps that are UTC ("2016-08-02T15:39:14.947").
# Spark's default session timezone is the JVM's, i.e. whatever the host machine is set to,
# so it would read those as local time and shift every timestamp by the local UTC offset.
# That is wrong, and worse, it makes the output depend on who ran the pipeline.
# Pinning to UTC makes ingestion reproducible on any machine.
SESSION_TIMEZONE = "UTC"


def get_spark(
    app_name: str = DEFAULT_APP_NAME,
    warehouse_dir: str = DEFAULT_WAREHOUSE_DIR,
) -> SparkSession:
    """Return an active SparkSession configured for Delta Lake."""
    existing = SparkSession.getActiveSession()
    if existing is not None:
        # A session already exists — this is the Databricks path, where the
        # platform provides one. We cannot rebuild it, but the timezone must
        # hold here too, otherwise the same code produces different timestamps
        # depending on where it runs.
        #
        # That session may be shared with other jobs on the same cluster, so
        # this is a side effect on state we do not own. We still apply it —
        # ingestion is wrong without it — but never silently: if the session
        # disagrees with us, say so loudly enough to be traceable.
        current = existing.conf.get("spark.sql.session.timeZone", None)
        if current != SESSION_TIMEZONE:
            logger.warning(
                "Overriding spark.sql.session.timeZone on a pre-existing session: %s -> %s. "
                "This session may be shared; the change is global and is not reverted.",
                current,
                SESSION_TIMEZONE,
            )
            existing.conf.set("spark.sql.session.timeZone", SESSION_TIMEZONE)
        return existing

    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.warehouse.dir", warehouse_dir)
        .config("spark.sql.session.timeZone", SESSION_TIMEZONE)
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()
