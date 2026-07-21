# src/dataflow — transformation logic

The library. Everything here is importable, testable, and free of orchestration
concerns. Nothing in this directory decides *when* it runs or *how* it is
triggered — that is `pipelines/` and `orchestration/`.

## Layout

```
bronze/     raw ingestion — XML in, typed Delta tables out
silver/     cleaned, validated, standardised   (moving to dbt)
gold/       business aggregations and marts    (moving to dbt)
common/     shared infrastructure
```

## The rule that matters

**Transformations are pure functions.** A function takes a DataFrame and returns
a DataFrame. It does not read files, write tables, create sessions, or read
config.

```python
def clean_columns(df: DataFrame) -> DataFrame:   # testable
def run(spark, source_path, table): ...          # orchestration, thin
```

I/O is confined to clearly-named functions (`load_*`, `write_*`) and to the
`run()` entrypoint that stitches them together. This split is why bronze can be
unit-tested against a 5-row fixture with no Spark cluster and no 191MB file.

## common/

| Module | Purpose |
|---|---|
| `spark.py` | The **only** place a SparkSession is built. Reuses an existing session when one exists — that is the Databricks path. |
| `config.py` | Loads `configs/pipeline.yaml`. Override the path with `DATAFLOW_CONFIG`. |
| `logging.py` | `get_logger(name)` — consistent formatting, no duplicate handlers. |

Modules deleted on purpose, do not resurrect them:

- `io.py` — a read/write wrapper with exactly one caller. Abstraction with a
  single consumer is cost without benefit.
- `schema.py` — a 4-field schema matching nothing real. The authoritative schema
  lives next to the code that reads it, in `bronze/posts.py`. Downstream
  contracts belong in dbt.
- `state.py` — hand-rolled watermark tracking. dbt incremental models do this
  natively and better.

## silver/ and gold/

Currently empty. The logic exists in `notebooks/silver_posts.ipynb`,
`notebooks/gold_*.ipynb` and is being ported to dbt, not to Python. These
packages will likely be removed once that port completes.
