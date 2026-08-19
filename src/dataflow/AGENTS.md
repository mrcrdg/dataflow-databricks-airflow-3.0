# src/dataflow — transformation logic

The library. Everything here is importable, testable, and free of orchestration
concerns. Nothing in this directory decides *when* it runs or *how* it is
triggered — that is `pipelines/` and `orchestration/`.

## Layout

```
bronze/     raw ingestion — XML in, typed Delta tables out
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

## Why there is no silver/ or gold/

There were empty `silver/` and `gold/` packages here. They are **deleted** — the
port went to dbt, not to Python, so nothing was ever going to fill them. Silver
and gold live in `dbt/models/`.

This is the only layer where Python earns its place: parsing XML is the one job
dbt cannot do. Once the data is a table, the work is SQL. See `AGENTS.md` at the
repo root for the full reasoning, and `docs/adr/0002` for why an artifact that
nothing exercises gets deleted rather than kept "for later".
