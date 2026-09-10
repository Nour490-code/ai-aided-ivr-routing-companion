# Environment
## Docker
    - docker-compose up -d
## Technologies
    - Spark: Batch processing
    - Kafka: Ingestion
    - Iceberg: Lakehouse storage
    - MinIO: Object storage
    - DuckDB: Querying
## Endpoints
    - Spark Master: http://localhost:8080
    - Spark Worker: http://localhost:8081
    - Kafka: http://localhost:9092
    - MinIO: http://localhost:9000
    
# Scripts by order

## 1. Ingestion

### Batch
Topic initialization: 

```bash
    docker exec -it kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --topic customer-commands-batch --partitions 1 --replication-factor 1
```

```bash
 docker exec -it spark-master /opt/spark/bin/spark-submit   --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2   /app/src/ingestion/kafka_batch_producer.py
 ```

### Streaming

Topic initialization: 
```bash
    docker exec -it kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --topic customer-commands-streaming --partitions 1 --replication-factor 1
```

```bash
 docker exec -it spark-master /opt/spark/bin/spark-submit   --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2   /app/src/ingestion/kafka_streaming_producer.py
```

## 2. Batch Pipeline

```bash
docker exec -it spark-master /opt/spark/bin/spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.2,org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0,org.apache.iceberg:iceberg-aws-bundle:1.5.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  /app/src/batch/iceberg_lakehouse.py
```

Note: DuckDB is not installed in the container, so install it locally inside ur terminal
```bash
pip install duckdb
```