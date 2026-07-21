-- Gold: the most-used tags by number of posts.
--
-- Ports notebooks/gold_most_popular_tags.ipynb, with two fixes:
--   1. The notebook's Hive `LATERAL VIEW explode` becomes DuckDB `unnest`.
--   2. The notebook ordered by post_count alone, so tags tied at the cutoff
--      swapped in and out between runs. Adding `tag` as a tiebreaker makes the
--      result deterministic.
-- The row limit is a var (default 100) because the notebook's code said 10
-- while its own docs said 100.

with exploded as (
    select
        post_id,
        unnest(tags_array) as tag
    from {{ ref('stg_posts') }}
    where tags_array is not null
)

select
    tag,
    count(distinct post_id) as post_count
from exploded
group by tag
order by post_count desc, tag
limit {{ var('top_tags_limit') }}
