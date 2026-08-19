# Running this project on Databricks

DuckDB is the default target and stays that way (ADR 0005). Databricks is
**opt-in**: it runs the same models, from the same repo, against a workspace.

This file is the setup, and the honest account of what "an adapter swap, not a
rewrite" actually cost.

## What the swap really required

ADR 0005 said moving to Databricks would be a swap of adapter. Nothing had ever
tested that, and it was not quite true. Three things in the models were DuckDB
dialect, not SQL:

| DuckDB | Databricks | Where |
|---|---|---|
| `string_split(s, '\|')` | `split(s, '\\\|')` — the delimiter is a regex here | `stg_posts` |
| `list_filter(a, x -> x <> '')` | `filter(a, x -> x <> '')` | `stg_posts` |
| `unnest(a)` | `explode(a)` | `marts_top_tags` |

Plus one that was not a function at all: the models quoted the bronze column
names (`p."Id"`), because the XML reader produces `Id`, `PostTypeId`,
`CreationDate`. **Databricks SQL reads a double-quoted token as a string
literal**, so every one of those would have compiled to a constant instead of a
column — the kind of failure that returns rows rather than an error.

All four are fixed. The three functions now go through `dbt/macros/portable_sql.sql`,
which dispatches on the adapter; the quotes are simply gone, because both
engines match unquoted identifiers case-insensitively.

**What did not need changing:** the sources. `external_location` lives under
`meta:`, which dbt-duckdb reads and every other adapter ignores — so
`{{ source('bronze', 'posts') }}` resolves to a `delta_scan()` locally and to the
table `bronze.posts` on Databricks, with no branching.

So the claim survives, but only just, and only now that something exercises it.

## What you need

A **Databricks Free Edition** account — free, no card, serverless only. It
replaced Community Edition on 1 January 2026 and includes a SQL warehouse and
AI/BI dashboards, which is what makes this worth doing at all.

1. Sign up at <https://www.databricks.com/learn/free-edition>.
2. In the workspace, open **SQL Warehouses** and note the running warehouse's
   **Server hostname** and **HTTP path** (Connection details tab).
3. Create a personal access token: avatar → **Settings** → **Developer** →
   **Access tokens** → *Generate new token*.

## Configuring it

Put the credentials in a file **outside the repo**, readable only by you:

```bash
umask 077
cat > ~/.dataflow-databricks.env <<'EOF'
export DATABRICKS_HOST=dbc-xxxxxxxx-xxxx.cloud.databricks.com
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxxxxxxxxxxx
export DATABRICKS_TOKEN=dapi...
export DATABRICKS_CATALOG=workspace
export DATABRICKS_SCHEMA=dataflow
EOF
```

The token is a password. It never goes in this repo, in `dbt/profiles.yml`, or
in a commit — `profiles.yml` reads all four from the environment, each with a
harmless default so a laptop that has never heard of Databricks can still run
`dbt build`.

## Running it

```bash
uv sync --group dbt --group databricks
source ~/.dataflow-databricks.env

dbt build --project-dir dbt --profiles-dir dbt --target databricks
```

That builds silver and gold **in the workspace**, from bronze tables that must
already be there.

## Getting bronze up there

dbt transforms tables; it does not create them from XML. Bronze has to exist in
the workspace first, and there are two ways:

**Upload what Spark already wrote** — the fast path. The local bronze job writes
Delta tables under `spark-warehouse/bronze.db/`. Upload them to a Unity Catalog
volume and register them:

```sql
create schema if not exists workspace.bronze;
create table workspace.bronze.posts as select * from delta.`/Volumes/.../posts`;
```

**Run the ingestion up there** — the honest path. `src/dataflow/bronze/` is plain
PySpark with no local assumptions, so it runs in a Databricks notebook against
the XML in a volume. This is the version that proves the whole pipeline moves,
not just the SQL.

Neither is done yet. The first is an afternoon; the second is a day, and needs
the 191 MB archive uploaded.

## What this does not change

- **DuckDB stays the default.** `dbt build` with no `--target` is local, needs no
  account, and is what CI runs.
- **CI does not test the Databricks target.** It cannot: that would need a
  workspace and a token in the repo's secrets. The dialect macros are exercised
  only on the DuckDB side, so the Databricks path is verified by running it, not
  by CI. That is a real gap, and it is the reason this file exists rather than a
  claim in the README.
