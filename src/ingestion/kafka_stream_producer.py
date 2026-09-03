from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import col

spark = SparkSession.builder \
    .appName("CSV-Streaming-Kafka-Producer") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2") \
    .getOrCreate()

# Run command:
    # docker exec -it spark-master /opt/spark/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2 /app/src/ingestion/kafka_stream_producer.py

DATA_SOURCE_PATH = "/app/data/Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
STREAMING_DATA_PATH = "/tmp/streaming-data"
KAFKA_BROKERS = "kafka:9092"
STREAM_TOPIC = "customer-commands-streaming"

schema = StructType([
    StructField("flags", StringType(), True),
    StructField("instruction", StringType(), True),
    StructField("category", StringType(), True),
    StructField("intent", StringType(), True)
])

# Read source CSV
raw_df = spark.read \
    .schema(schema) \
    .option("header", "true") \
    .option("delimiter", ",") \
    .option("multiline", "true") \
    .option("escape", "\"") \
    .csv(DATA_SOURCE_PATH)

# Dump into temporary directory to trigger the stream simulation
raw_df.write \
    .mode("overwrite") \
    .json(STREAMING_DATA_PATH)

print("🚀 Launching Stream Monitoring...")

raw_stream_df = spark.readStream \
    .schema(schema) \
    .format("json") \
    .load(STREAMING_DATA_PATH)

kafka_stream_df = raw_stream_df.select(
    col("flags").cast("string").alias("key"),
    col("instruction").cast("string").alias("value")
)

stream_query = kafka_stream_df.writeStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
    .option("topic", STREAM_TOPIC) \
    .option("checkpointLocation", "/tmp/spark-kafka-checkpoint-stream") \
    .outputMode("append") \
    .start()

stream_query.awaitTermination()