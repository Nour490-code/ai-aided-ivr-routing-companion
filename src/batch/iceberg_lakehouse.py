from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import col, from_json

spark = SparkSession.builder \
    .appName("Kafka-To-Iceberg-Batch-Consumer") \
    .config("spark.sql.catalog.demo", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.demo.type", "rest") \
    .config("spark.sql.catalog.demo.uri", "http://iceberg-rest:8181") \
    .config("spark.sql.catalog.demo.warehouse", "s3://warehouse/") \
    .config("spark.sql.catalog.demo.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
    .config("spark.sql.catalog.demo.s3.endpoint", "http://minio:9000") \
    .config("spark.sql.catalog.demo.s3.path-style-access", "true") \
    .config("spark.sql.catalog.demo.client.region", "us-east-1") \
    .config("spark.sql.catalog.demo.s3.access-key-id", "admin") \
    .config("spark.sql.catalog.demo.s3.secret-access-key", "password123") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "admin") \
    .config("spark.hadoop.fs.s3a.secret.key", "password123") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .getOrCreate()

KAFKA_BROKERS = "kafka:9092"
BATCH_TOPIC = "customer-commands-batch"

payload_schema = StructType([
    StructField("instruction", StringType(), True),
    StructField("intent", StringType(), True)
])

print("🚀 Reading batch records from Kafka topic...")

kafka_df = spark.read \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
    .option("subscribe", BATCH_TOPIC) \
    .option("startingOffsets", "earliest") \
    .option("endingOffsets", "latest") \
    .load()

parsed_df = kafka_df.select(
    col("key").cast("string").alias("command_key"),
    from_json(col("value").cast("string"), payload_schema).alias("payload"),
    col("timestamp").alias("kafka_timestamp")
).select(
    col("command_key"),
    col("payload.instruction").alias("instruction"),
    col("payload.intent").alias("intent"),
    col("kafka_timestamp")
)

spark.sql("CREATE DATABASE IF NOT EXISTS demo.lakehouse;")

spark.sql("""
    CREATE TABLE IF NOT EXISTS demo.lakehouse.customer_commands_batch (
        command_key STRING,
        instruction STRING,
        intent STRING,
        kafka_timestamp TIMESTAMP
    ) USING iceberg;
""")

print("📦 Writing batch dataset to Iceberg Lakehouse on MinIO...")

parsed_df.write \
    .format("iceberg") \
    .mode("append") \
    .save("demo.lakehouse.customer_commands_batch")

print("✅ Ingestion complete: Batch data stored in Lakehouse.")



# docker exec -it spark-master /opt/spark/bin/spark-submit \
#   --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2,org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0,org.apache.iceberg:iceberg-aws-bundle:1.5.0,org.apache.hadoop:hadoop-aws:3.3.4 \
#   /app/src/batch/iceberg_lakehouse.py