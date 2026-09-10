from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import col, to_json, struct, lit

#  docker exec -it spark-master /opt/spark/bin/spark-submit   --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2   /app/src/ingestion/kafka_stream_producer.py

spark = SparkSession.builder \
    .appName("Parquet-to-Kafka-Producer-Stream") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2") \
    .getOrCreate()

PARQUET_SOURCE_PATH = "/app/data/test_split.parquet"
STREAMING_DATA_DIR = "/tmp/streaming-source"
KAFKA_BROKERS = "kafka:9092"
STREAM_TOPIC = "customer-commands-streaming"

schema = StructType([
    StructField("instruction", StringType(), True),
    StructField("intent", StringType(), True)
])

# Dump source Parquet file into temporary directory to trigger the stream simulation
source_df = spark.read.schema(schema).parquet(PARQUET_SOURCE_PATH)

source_df.write \
    .mode("overwrite") \
    .parquet(STREAMING_DATA_DIR)

print("Launching Stream Monitoring...")

raw_stream_df = spark.readStream \
    .schema(schema) \
    .format("parquet") \
    .load(STREAMING_DATA_DIR)

kafka_stream_df = raw_stream_df.select(
    lit("unknown_intent").cast("string").alias("key"),
    to_json(struct(col("instruction").cast("string"))).alias("value")
)

stream_query = kafka_stream_df.writeStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
    .option("topic", STREAM_TOPIC) \
    .option("checkpointLocation", "/tmp/spark-kafka-checkpoint-stream") \
    .outputMode("append") \
    .start()

stream_query.awaitTermination()