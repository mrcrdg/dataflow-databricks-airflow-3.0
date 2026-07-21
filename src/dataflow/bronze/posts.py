from pyspark.sql import DataFrame
from pyspark.sql.types import StructType, StructField, LongType, StringType, TimestampType
from pyspark.sql.functions import col
import logging

logger = logging.getLogger("bronze.posts")
logger.setLevel(logging.INFO)

POSTS_SCHEMA = StructType([
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
    StructField("_ViewCount", LongType(), True)
])


def load_raw_posts(spark, path: str) -> DataFrame:
    return (
        spark.read.format("xml")
        .option("rootTag", "posts")
        .option("rowTag", "row")
        .schema(POSTS_SCHEMA)
        .load(path)
    )


def clean_columns(df: DataFrame) -> DataFrame:
    renamed = {
        c: c.replace("_", "")
        for c in df.columns
    }
    return df.select([col(c).alias(renamed[c]) for c in df.columns])


def write_to_delta(df: DataFrame, table_name: str):
    (
        df.write
        .mode("overwrite")
        .format("delta")
        .option("overwriteSchema", "true")
        .saveAsTable(table_name)
    )


def run(spark, input_path: str, table_name: str):
    logger.info("🚀 Starting bronze ingestion pipeline")

    logger.info(f"Reading input data from: {input_path}")
    df = load_raw_posts(spark, input_path)

    logger.info("Applying transformations (clean_columns)")
    df = clean_columns(df)

    rows_before = df.count()
    logger.info(f"Rows after transformation: {rows_before}")

    logger.info(f"Writing data to Delta table: {table_name}")
    write_to_delta(df, table_name)

    logger.info("Write completed successfully")

    return df