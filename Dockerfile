FROM apache/spark:3.5.0

USER root

WORKDIR /app

COPY . /app

RUN pip install pyspark delta-spark

ENV PYTHONPATH=/app