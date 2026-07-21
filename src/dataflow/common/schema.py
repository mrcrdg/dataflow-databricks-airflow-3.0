from pyspark.sql.types import *

# schema enforcement (Data Contract v1)


POSTS_SCHEMA_V1 = StructType([
    StructField("id", IntegerType(), False),
    StructField("user_id", IntegerType(), True),
    StructField("title", StringType(), True),
    StructField("created_at", TimestampType(), True),
])