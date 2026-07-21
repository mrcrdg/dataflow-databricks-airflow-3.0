"""Bronze ingestion for the Stack Exchange Posts dump.

Reads raw Posts.xml, strips the leading underscore the XML reader puts on every
attribute name, and lands the result as a Delta table. No business logic here —
bronze is a faithful, typed copy of the source. Cleaning happens in silver.
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

logger = get_logger("dataflow.bronze.posts")

# Explicit schema rather than inferring: schema inference on a 49MB XML file
# means a full extra pass over the data, and lets the source silently change
# types on us between runs.
POSTS_SCHEMA = StructType(
    [
        StructField("_AcceptedAnswerId", LongType(), True),
        StructField("_AnswerCount", LongType(), True),
        StructField("_Body", StringType(), True),
        StructField("_ClosedDate", TimestampType(), True),
        StructField("_CommentCount", LongType(), True),
        StructField("_CommunityOwnedDate", TimestampType(), True),
        StructField("_ContentLicense", StringType(), True),
        StructField("_CreationDate", TimestampType(), True),
        StructField("_FavoriteCount", LongType(), True),
        StructField("_Id", LongType(), True),
        StructField("_LastActivityDate", TimestampType(), True),
        StructField("_LastEditDate", TimestampType(), True),
        StructField("_LastEditorDisplayName", StringType(), True),
        StructField("_LastEditorUserId", LongType(), True),
        StructField("_OwnerDisplayName", StringType(), True),
        StructField("_OwnerUserId", LongType(), True),
        StructField("_ParentId", LongType(), True),
        StructField("_PostTypeId", LongType(), True),
        StructField("_Score", LongType(), True),
        StructField("_Tags", StringType(), True),
        StructField("_Title", StringType(), True),
        StructField("_ViewCount", LongType(), True),
    ]
)


def load_raw_posts(
    spark: SparkSession,
    path: str,
    root_tag: str = "posts",
    row_tag: str = "row",
) -> DataFrame:
    """Read Posts.xml into a DataFrame using the declared schema."""
    return (
        spark.read.format("xml")
        .option("rootTag", root_tag)
        .option("rowTag", row_tag)
        .schema(POSTS_SCHEMA)
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
    root_tag: str = "posts",
    row_tag: str = "row",
    write_mode: str = "overwrite",
) -> int:
    """Run the bronze posts ingestion. Returns the number of rows written."""
    logger.info("Reading raw posts from %s", source_path)
    df = clean_columns(load_raw_posts(spark, source_path, root_tag, row_tag))

    row_count = df.count()
    logger.info("Writing %s rows to %s (mode=%s)", row_count, table, write_mode)
    write_to_delta(df, table, write_mode)

    logger.info("Bronze posts ingestion complete")
    return row_count
