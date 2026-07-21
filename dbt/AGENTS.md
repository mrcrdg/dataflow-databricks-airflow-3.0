# dbt — silver and gold

Everything downstream of bronze. Bronze is a Delta table written by Spark; dbt
reads it and builds silver + gold as SQL.

## Run it

```bash
# bronze must exist first: python pipelines/bronze_posts.py
dbt build   --project-dir dbt --profiles-dir dbt   # seed + models + tests
dbt test    --project-dir dbt --profiles-dir dbt   # tests only
dbt docs generate --project-dir dbt --profiles-dir dbt
```

Invoke from the repo root — the Delta path and the DuckDB file are both
relative to it.

## How dbt reads bronze

DuckDB's `delta_scan()`, wired through a dbt source. `models/staging/_bronze__sources.yml`
sets `external_location: "delta_scan('{{ var('bronze_posts_path') }}')"`, so
`{{ source('bronze', 'posts') }}` reads the Delta table in place. **No copy** —
one storage layer, and the same table Databricks would read in production.

## Layout

```
seeds/post_types.csv       PostTypeId -> label lookup (was an in-notebook DataFrame)
models/staging/
  _bronze__sources.yml     the Delta table as a dbt source
  stg_posts.sql            silver: clean, type, tag-split, label      (view)
  stg_posts.yml            tests + docs
models/marts/
  marts_top_tags.sql       gold: top-N tags by post count             (table)
tests/                     singular tests (one SQL query = one assertion)
```

Staging models are **views** (cheap, always fresh); marts are **tables** (they
get queried, so materialise once).

## Conventions

- **snake_case everywhere.** The notebooks used PascalCase (`PostId`); silver
  renames on the way in. Bronze columns are the only PascalCase left, and they
  are quoted (`p."Id"`) because that is how they exist in Delta.
- **Explicit column lists**, never `select *` out of a model. The notebook's
  column order was an accident of a Spark join; do not reproduce it.
- **Every model has a `.yml`** with a description and at least a key test.
- Naming: `stg_` for staging, `marts_` for gold. Inherited from the notebooks.

## Fixes made while porting

The notebooks had defects; these were corrected here, not carried over:

- **Empty-vs-null tags.** The original validation would fail on every answer
  (answers have no tags). The array is NULL for a tagless post, never empty; the
  test checks for that exact property.
- **Non-deterministic top tags.** `ORDER BY post_count DESC` alone let tied tags
  swap at the cutoff. Added `tag` as a tiebreaker.
- **Limit contradiction.** Notebook code said 10, its docs said 100. Now
  `var('top_tags_limit')`, default 100.
- **Unmapped post types.** Ids not in the seed become `'Unknown'`, not NULL.

## Not here yet

`marts_posts_users` — needs a bronze `users` table, which does not exist yet
(`src/dataflow/bronze/users.py` is an empty stub). That is the next increment.
