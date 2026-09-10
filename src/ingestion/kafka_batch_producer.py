from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import col, to_json, struct, lit

spark = SparkSession.builder \
    .appName("Parquet-to-Kafka-Producer-Batch") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2") \
    .getOrCreate()

#  docker exec -it spark-master /opt/spark/bin/spark-submit   --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2   /app/src/ingestion/kafka_batch_producer.py

PARQUET_SOURCE_PATH = "/app/data/test_split.parquet"
KAFKA_BROKERS = "kafka:9092"
BATCH_TOPIC = "customer-commands-batch"
STREAM_TOPIC = "customer-commands-streaming"

schema = StructType([
    StructField("instruction", StringType(), True),
    StructField("intent", StringType(), True)
])

# Read source Parquet file
parquet_df = spark.read \
    .schema(schema) \
    .parquet(PARQUET_SOURCE_PATH)

print("Starting Batch Processing")

# Batch payload includes both instruction and intent
kafka_batch_df = parquet_df.select(
    col("intent").cast("string").alias("key"),
    to_json(struct("instruction", "intent")).alias("value")
)

kafka_batch_df.write \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
    .option("topic", BATCH_TOPIC) \
    .save()

print("Batch transfer complete.")