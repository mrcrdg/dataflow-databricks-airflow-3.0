# viz — looking at the gold tables

One script. It queries the gold tables and writes a self-contained HTML page.

```bash
python viz/build_dashboard.py           # -> viz/out/gold-dashboard.html
python viz/build_dashboard.py ci.duckdb /tmp/page.html
```

Open the result in a browser. There is no server, no build step and no asset
folder — the charts are SVG written by the script itself.

## The rule

**The output is generated, so it is not committed.** `viz/out/` is gitignored.
A committed page would be an artifact nothing regenerates, free to drift away
from the tables it claims to describe — the same trap as the config that
described a CSV which never existed (ADR 0002). Rerun the script instead.

**The script is exercised by `tests/viz/`**, which builds a page from a five-row
fixture database and asserts the structural properties: a real document with a
doctype and charset, no external assets beyond Google Fonts, and every colour
token defined outside a theme block. Those tests already caught two bugs — a
crash on any database with an empty score band, and a page that rendered from an
empty database instead of failing.

## Why a script and not a BI tool

Metabase, Superset and Evidence were considered; the reasoning is in
`ROADMAP.md` § Visualisation. The short version: a BI server holding the DuckDB
file open blocks `dbt build` from writing it, because DuckDB allows one writer at
a time. A script that runs, writes a file and exits has no such conflict.

This is the cheap option, not the final one. A warehouse that several processes
can read at once — Databricks, see `docs/databricks.md` — is where a real BI
tool belongs.

## What is deliberately not here

- **No chart library.** The page has no runtime dependency at all, which is what
  lets it open from a filesystem in ten years.
- **No colours picked by eye.** The palette was checked with a contrast and
  colour-blindness validator: the two series clear ΔE 18.9, and the ordinal ramp
  reverses direction in dark mode so the largest band does not vanish into the
  background.
- **No numbers hardcoded.** Every value on the page comes from a query. If a
  model changes shape, the page changes with it or the tests fail.
