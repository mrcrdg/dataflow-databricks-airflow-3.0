from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

from src.dataflow.bronze.posts import run
from pyspark.sql import SparkSession


def create_spark():
    return SparkSession.builder \
        .appName("airflow-bronze-posts") \
        .getOrCreate()


def run_pipeline():
    spark = create_spark()

    run(
        spark,
        "data/ai.stackexchange.com/Posts.xml",
        "bronze.posts"
    )

    spark.stop()


default_args = {
    "owner": "data-platform",
    "start_date": datetime(2025, 1, 1),
}

with DAG(
    dag_id="bronze_posts_pipeline",
    default_args=default_args,
    schedule_interval="@daily",
    catchup=False,
) as dag:

    task_run_bronze = PythonOperator(
        task_id="run_bronze_posts",
        python_callable=run_pipeline
    )