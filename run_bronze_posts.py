from pyspark.sql import SparkSession
from src.dataflow.bronze.posts import run
from delta import configure_spark_with_delta_pip


def create_spark():
    builder = (
        SparkSession.builder
        .appName("lakehouse-local")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.warehouse.dir", "./spark-warehouse")
    )

    return configure_spark_with_delta_pip(builder).getOrCreate()

def main():
    spark = create_spark()

    spark.sql("CREATE DATABASE IF NOT EXISTS bronze")

    input_path = "data/ai.stackexchange.com/Posts.xml"

    # IMPORTANT: use FULL table name (like Databricks style)
    table_name = "bronze.posts"

    print("🚀 Running pipeline...")

    df = run(spark, input_path, table_name)

    print(f"✅ Done. Rows: {df.count()}")

    print("📊 Checking table:")
    spark.sql("SHOW TABLES IN bronze").show()

    spark.sql("SELECT COUNT(*) FROM bronze.posts").show()

    spark.stop()


if __name__ == "__main__":
    main()