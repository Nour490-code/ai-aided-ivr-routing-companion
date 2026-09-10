FROM apache/spark:3.5.6-python3

WORKDIR /app

USER root

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt