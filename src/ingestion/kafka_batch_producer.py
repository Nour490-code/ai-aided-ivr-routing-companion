from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import col, to_json, struct

spark = SparkSession.builder \
    .appName("CSV-Batch-Kafka-Producer") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2") \
    .getOrCreate()

# Run command:
    #  docker exec -it spark-master /opt/spark/bin/spark-submit   --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2   /app/src/ingestion/kafka_batch_producer.py

DATA_SOURCE_PATH = "/app/data/Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
KAFKA_BROKERS = "kafka:9092"
BATCH_TOPIC = "customer-commands-batch"
STREAM_TOPIC = "customer-commands-streaming"


schema = StructType([
    StructField("flags", StringType(), True),
    StructField("instruction", StringType(), True),
    StructField("category", StringType(), True),
    StructField("intent", StringType(), True)
])

raw_df = spark.read \
    .schema(schema) \
    .option("header", "true") \
    .option("delimiter", ",") \
    .option("multiline", "true") \
    .option("escape", "\"") \
    .csv(DATA_SOURCE_PATH)


print("🚀 Starting Batch Processing...")

kafka_batch_df = raw_df.select(
    col("intent").cast("string").alias("key"),
    to_json(struct("flags","instruction" ,"category")).alias("value")
)


kafka_batch_df.write \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
    .option("topic", BATCH_TOPIC) \
    .save()

print("✅ Batch transfer complete.")
