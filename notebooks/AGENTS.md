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
| `bronze_users.ipynb` | **Ported** → `src/dataflow/bronze/users.py` |
| `silver_posts.ipynb` | **Ported** → `dbt/models/staging/stg_posts.sql` |
| `gold_most_popular_tags.ipynb` | **Ported** → `dbt/models/marts/marts_top_tags.sql` |
| `gold_posts_users.ipynb` | **Ported** → `dbt/models/marts/marts_posts_users.sql` |
| `bronze_posts_dqx.ipynb` | Databricks-only (DQX). No local equivalent. |

## Why they cannot be run as-is

They target a Databricks workspace (`data-plataform-jayzern`) and read from
`/Volumes/...` paths. Without that workspace they do not execute. This is
precisely the problem the port solves: notebook logic that only runs in one
place, for one person.

## Porting notes

`silver_posts.ipynb` was the valuable one, and it ported cleanly: its
transformations were already pure functions (`normalize_tags`,
`standardize_post_schema`, `map_post_type`) chained with `.transform()`, so the
logic moved to `stg_posts.sql` almost directly, and `validate_stg_posts` became
dbt tests.

`gold_posts_users.ipynb` carried two defects. Both were fixed during the port
rather than reproduced, and are written up in `dbt/AGENTS.md`:

- it dropped `owner_user_id` from the output, so a post whose user did not match
  lost the id entirely and a failed join became impossible to debug
- it assumed one row per user without checking. A duplicate would have fanned
  out the join and broken the one-row-per-post grain silently.

`bronze_users.ipynb` had a third, harmless one worth knowing about: it read
Users.xml with `rootTag="posts"`, copy-pasted from the posts notebook, and
worked anyway — on read, Spark's XML reader ignores `rootTag` entirely. Only
`rowTag` selects rows, and getting *that* wrong returns an empty DataFrame
rather than an error. Pinned by
`tests/bronze/test_users.py::test_a_wrong_row_tag_yields_no_rows_rather_than_an_error`.

The gold notebooks are already `%sql` — `CREATE OR REPLACE TABLE ... SELECT`
with `stg_` and `marts_` naming. That is dbt convention written by hand; the SQL
moves into dbt models with little change.
