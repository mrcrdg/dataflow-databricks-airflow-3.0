# notebooks — frozen prototypes

**These are historical. Do not add production logic here, and do not treat them
as the source of truth.**

They are the original Databricks implementation, kept because they document how
the pipeline was explored and because the silver/gold logic is still being
ported out of them.

## What is here

| Notebook | Status |
|---|---|
| `bronze_posts.ipynb` | **Ported** → `src/dataflow/bronze/posts.py` |
| `bronze_users.ipynb` | Not ported — same pattern as posts |
| `silver_posts.ipynb` | **Next to port** → dbt models |
| `gold_posts_users.ipynb` | To port → dbt mart |
| `gold_most_popular_tags.ipynb` | To port → dbt mart |
| `bronze_posts_dqx.ipynb` | Databricks-only (DQX). No local equivalent. |

## Why they cannot be run as-is

They target a Databricks workspace (`data-plataform-jayzern`) and read from
`/Volumes/...` paths. Without that workspace they do not execute. This is
precisely the problem the port solves: notebook logic that only runs in one
place, for one person.

## Porting notes

`silver_posts.ipynb` is the valuable one. Its transformations are already written
as pure functions (`normalize_tags`, `standardize_post_schema`, `map_post_type`)
chained with `.transform()`, so the logic translates to dbt models almost
directly. `validate_stg_posts` becomes dbt tests.

The gold notebooks are already `%sql` — `CREATE OR REPLACE TABLE ... SELECT`
with `stg_` and `marts_` naming. That is dbt convention written by hand; the SQL
moves into dbt models with little change.
