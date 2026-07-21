# Data Platform: Modular Lakehouse Architecture

A production platform data engineering project designed to support scalable batch/stream processing workflows across multiple execution environments such as Databricks, Airflow, or Kubernetes.

---

## Overview

This project implements a **modular, multi-layered data architecture** following industry best practices for modern data engineering systems.

It is designed to be:

- **Platform-agnostic** (runs on Databricks, Airflow, or Kubernetes)
- **Testable and modular**
- **Production-ready structure**
- **Cloud and Spark compatible**
- **Easily extensible for new pipelines and data domains**

---

## Architecture

The project follows a layered architecture:

```
src/
├── bronze/ → raw ingestion and minimal cleaning
├── silver/ → cleaned, validated datasets
├── gold/ → business-level aggregations
├── common/ → shared utilities (Spark, IO, config)
```

### Execution Flow


Raw Data → Bronze → Silver → Gold → Analytics/Consumption


---

## Key Design Principles

### 1. Separation of Concerns
- Business logic is isolated from execution logic
- Pipelines are independent and reusable

### 2. Platform Independence
The same codebase can run on:
- Databricks Jobs
- Apache Airflow DAGs
- Kubernetes containers

### 3. Code-First Development
- No production logic inside notebooks
- All transformations are written in Python modules

### 4. Testability
- Each transformation is unit-testable
- Spark logic is isolated for reproducibility

---

## Project Structure


```
dataflow-project/
│
├── src/
│   └── dataflow/
│       │
│       ├── bronze/
│       │   ├── posts.py             #  production ingestion 
│       │   ├── users.py             # empty 
│       │
│       ├── silver/
│       │   ├── posts.py             # empty 
│       │
│       ├── gold/
│       │   ├── analytics.py         # empty 
│       │   ├── tags.py              # empty 
│       │
│       ├── common/
│       │   ├── spark.py             # empty 
│       │   ├── io.py                # empty 
│       │   ├── config.py            # empty 
│       │   ├── state.py            # empty 
│       │   ├── logger.py           # empty 
│       │   ├── schema_registry.py  # empty 
│
├── data/
│   ├── Posts.xml               # my data source 
│   ├── Users.xml           # my data source 
│
├── pipelines/
│   │
│   ├── bronze/
│   │   ├── posts.py                # calls src/dataflow/bronze/posts.run()
│   │   ├── users.py                # empty 
│   │
│   ├── silver/
│   │   ├── posts.py                # empty 
│   │
│   ├── gold/
│   │   ├── analytics.py
│   │
│   ├── run_all.py                  # empty 
│
├── orchestration/
│   │
│   ├── airflow_dags/
│   │   ├── posts_dag.py            # empty 
│   │
│   ├── databricks_jobs/
│   │   ├── bronze_posts_job.json   # empty 
│
├── configs/
│   ├── pipeline.yaml               # empty 
│   ├── environments.yaml           # empty 
│
├── notebooks/
│   ├── exploration/
│   │   ├── bronze_posts.ipynb     # only for experimentation
│   │   ├── bronze_users.ipynb
│
├── tests/
│   ├── bronze/
│   │   ├── test_posts.py          # empty
│   │
│   ├── silver/
│   ├── gold/
│
├── scripts/
│   ├── run_bronze_posts.py        # empty
│   ├── run_silver_posts.py
│
├── requirements.txt
└── README.md
```



```
dataflow-project/
│
├── src/
│   └── dataflow/
│       │
│       ├── bronze/
│       │   ├── posts.py             #  production ingestion 
│       │   ├── users.py             # (to be upgraded next)
│       │
│       ├── silver/
│       │   ├── posts.py             # (next layer: cleaning + joins)
│       │
│       ├── gold/
│       │   ├── analytics.py         # (KPIs / business metrics)
│       │   ├── tags.py              # (aggregations / insights)
│       │
│       ├── common/
│       │   ├── spark.py             # Spark session factory (NEW responsibility)
│       │   ├── io.py                # read/write utilities (NEW abstraction layer)
│       │   ├── config.py            # YAML loader (config-driven pipelines)
│       │   ├── state.py            # NEW: pipeline state tracking (watermarks)
│       │   ├── logger.py           # EW: metrics + logging
│       │   ├── schema_registry.py  # (future: schema versioning)
│
├── pipelines/
│   │
│   ├── bronze/
│   │   ├── posts.py                # calls src/dataflow/bronze/posts.run()
│   │   ├── users.py                # same pattern (to implement next)
│   │
│   ├── silver/
│   │   ├── posts.py                # orchestration layer only
│   │
│   ├── gold/
│   │   ├── analytics.py
│   │
│   ├── run_all.py                  # (optional: full DAG-like execution entrypoint)
│
├── orchestration/
│   │
│   ├── airflow_dags/
│   │   ├── posts_dag.py            # DAG calling bronze → silver → gold
│   │
│   ├── databricks_jobs/
│   │   ├── bronze_posts_job.json   # job definitions
│
├── configs/
│   ├── pipeline.yaml               # now actually used (source, tables, mode)
│   ├── environments.yaml           # (dev/staging/prod configs - optional next step)
│
├── notebooks/
│   ├── exploration/
│   │   ├── bronze_posts.ipynb     # only for experimentation
│   │   ├── bronze_users.ipynb
│   │
│   ├── deprecated/
│   │   ├── bronze_posts_old.ipynb # move old logic here (important discipline)
│
├── tests/
│   ├── bronze/
│   │   ├── test_posts.py          # schema + validation tests
│   │
│   ├── silver/
│   ├── gold/
│
├── scripts/
│   ├── run_bronze_posts.py        # local execution entrypoint
│   ├── run_silver_posts.py
│
├── requirements.txt
└── README.md
```

---

## How It Works

### 1. Development (Local)
Developers write and test transformations locally using Python and Spark.

### 2. Execution Layer
Pipelines are executed in:
- Databricks clusters
- Kubernetes jobs
- Airflow tasks

### 3. Orchestration Layer
Workflows are triggered and managed via:
- Airflow (scheduled workflows)
- Databricks Jobs (managed execution)

---

## Example Pipeline Flow

### Bronze Layer (Raw ingestion)
- Reads raw data from storage
- Applies minimal cleaning
- Stores structured raw datasets

### Silver Layer (Cleaned data)
- Deduplication
- Data validation
- Standardization

### Gold Layer (Business logic)
- Aggregations
- Metrics
- Analytics-ready datasets

---

## Testing Strategy

Each transformation is designed to be testable:

- Unit tests for transformation logic
- Spark session fixtures for reproducibility
- Data validation checks in pipelines

---

## Technologies (Optional / Extendable)

- Python
- Apache Spark
- Databricks
- Airflow (optional orchestration)
- Kubernetes (optional execution layer)
- Git-based CI/CD

---

## Example Usage

```bash
# Run a pipeline locally
python pipelines/bronze_posts.py
# Run tests
pytest tests/