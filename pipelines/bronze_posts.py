from src.dataflow.bronze.posts import run

def run_bronze_posts_job(spark):
    input_path = "data/ai.stackexchange.com/Posts.xml"
    table_name = "bronze.posts"

    print("🚀 Starting Bronze Posts Job")

    df = run(spark, input_path, table_name)

    print(f"✅ Finished Bronze Posts Job | rows={df.count()}")

    return df