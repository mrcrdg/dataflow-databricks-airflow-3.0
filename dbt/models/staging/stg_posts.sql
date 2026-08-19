-- Silver: cleaned, typed posts.
--
-- Ports notebooks/silver_posts.ipynb. Three things happen here, matching the
-- notebook's three .transform() steps:
--   1. rename Id -> post_id, and everything to snake_case
--   2. pipe-delimited Tags string -> a tags_array
--   3. map post_type_id -> a human label via the post_types seed
--
-- Explicit column list on purpose: the notebook's column order was an accident
-- of how Spark hoists a join key, and should not be reproduced.

with posts as (
    select * from {{ source('bronze', 'posts') }}
),

post_types as (
    select * from {{ ref('post_types') }}
),

final as (
    select
        p.Id                    as post_id,
        p.PostTypeId            as post_type_id,
        -- Unknown rather than null for any id not in the seed (e.g. 11, 16),
        -- so a new post type surfaces as a visible label, not a null hole.
        coalesce(pt.post_type, 'Unknown') as post_type,
        p.ParentId              as parent_id,
        p.AcceptedAnswerId      as accepted_answer_id,

        p.OwnerUserId           as owner_user_id,
        p.OwnerDisplayName      as owner_display_name,
        p.LastEditorUserId      as last_editor_user_id,
        p.LastEditorDisplayName as last_editor_display_name,

        p.Title                 as title,
        p.Body                  as body,
        -- "|a|b|c|" -> ['a','b','c']. Splitting NULL yields NULL, so posts
        -- with no tags (answers) get a NULL array, not an empty one — the
        -- filter drops the empty leading/trailing elements the pipes create.
        -- Both calls go through macros/portable_sql.sql: the function names
        -- differ between DuckDB and Databricks, the meaning does not.
        {{ filter_non_empty(split_string('p.Tags', '|')) }} as tags_array,

        p.Score                 as score,
        p.ViewCount             as view_count,
        p.AnswerCount           as answer_count,
        p.CommentCount          as comment_count,
        p.FavoriteCount         as favorite_count,

        p.ContentLicense        as content_license,
        p.CreationDate          as creation_date,
        p.LastActivityDate      as last_activity_date,
        p.LastEditDate          as last_edit_date,
        p.ClosedDate            as closed_date,
        p.CommunityOwnedDate    as community_owned_date

    from posts p
    left join post_types pt on p.PostTypeId = pt.post_type_id
)

select * from final
