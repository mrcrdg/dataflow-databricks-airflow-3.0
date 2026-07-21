"""Incremental processing state (watermark tracking).

SUPERSEDED — kept only as a record of the original sketch.

The plan was to hand-roll watermark tracking here: read the last processed
timestamp, filter the dataframe, write the new high-water mark back.

This is now dbt's job. dbt incremental models handle watermarks natively via
`is_incremental()`, so re-implementing it here would be duplicated logic with
worse tooling. This module is scheduled for deletion once silver/gold move to
dbt (see ROADMAP.md).

Original sketch:

    last_ts = get_last_processed("posts")
    df = df.filter(df.created_at > last_ts)
    update_last_processed("posts", max_timestamp)
"""
