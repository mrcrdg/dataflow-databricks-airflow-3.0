"""Bronze ingestion for the Stack Exchange Users dump.

Reads raw Users.xml, strips the leading underscore the XML reader puts on every
attribute name, and lands the result as a Delta table. No business logic here —
bronze is a faithful, typed copy of the source. Cleaning happens in silver.

Deliberately mirrors `bronze/posts.py` rather than sharing a generic ingest
helper with it. The two modules differ in schema, column set and log lines, so a
shared helper would be parameterised on almost everything it does — the same
trade that got `common/io.py` deleted. See `src/dataflow/AGENTS.md`.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col
from pyspark.sql.types import (
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from dataflow.common.logging import get_logger

logger = get_logger("dataflow.bronze.users")

# Explicit schema rather than inferring, for the same reasons as posts: no extra
# pass over the file, and the source cannot silently change types between runs.
USERS_SCHEMA = StructType(
    [
        StructField("_AboutMe", StringType(), True),
        StructField("_AccountId", LongType(), True),
        StructField("_CreationDate", TimestampType(), True),
        StructField("_DisplayName", StringType(), True),
        StructField("_DownVotes", LongType(), True),
        StructField("_Id", LongType(), True),
        StructField("_LastAccessDate", TimestampType(), True),
        StructField("_Location", StringType(), True),
        StructField("_Reputation", LongType(), True),
        StructField("_UpVotes", LongType(), True),
        StructField("_Views", LongType(), True),
        StructField("_WebsiteUrl", StringType(), True),
    ]
)


def load_raw_users(
    spark: SparkSession,
    path: str,
    row_tag: str = "row",
) -> DataFrame:
    """Read Users.xml into a DataFrame using the declared schema."""
    # No `rootTag` option: on read, Spark's XML reader ignores it entirely —
    # only `rowTag` selects rows. Setting it suggested a control that did not
    # exist. See tests/bronze/test_users.py for the failure mode.
    return (
        spark.read.format("xml")
        .option("rowTag", row_tag)
        .schema(USERS_SCHEMA)
        .load(path)
    )


def clean_columns(df: DataFrame) -> DataFrame:
    """Strip the leading underscore the XML reader prefixes onto attributes.

    Pure transformation: DataFrame in, DataFrame out, no I/O. This is what
    makes the layer unit-testable.
    """
    return df.select([col(c).alias(c.lstrip("_")) for c in df.columns])


def write_to_delta(df: DataFrame, table: str, mode: str = "overwrite") -> None:
    """Persist the DataFrame as a managed Delta table."""
    (
        df.write.mode(mode)
        .format("delta")
        .option("overwriteSchema", "true")
        .saveAsTable(table)
    )


def run(
    spark: SparkSession,
    source_path: str,
    table: str,
    row_tag: str = "row",
    write_mode: str = "overwrite",
) -> int:
    """Run the bronze users ingestion. Returns the number of rows written."""
    logger.info("Reading raw users from %s", source_path)
    df = clean_columns(load_raw_users(spark, source_path, row_tag))

    row_count = df.count()
    logger.info("Writing %s rows to %s (mode=%s)", row_count, table, write_mode)
    write_to_delta(df, table, write_mode)

    logger.info("Bronze users ingestion complete")
    return row_count
