-- Gold: one big table — every post enriched with its author.
--
-- Ports notebooks/gold_posts_users.ipynb. Grain: one row per post. Users are
-- the dimension side, so the join is a LEFT JOIN — a post whose author is
-- missing (deleted account, anonymous edit) keeps the post.
--
-- One fix over the notebook: it selected `u.Id as UserId` and never carried
-- p.OwnerUserId through. When the join missed, UserId came back NULL and the
-- post's author id was gone from the output entirely — indistinguishable from
-- a post that never had one, and impossible to debug against the source.
-- Here owner_user_id comes from the post and is always populated when the
-- source had it; user_id comes from the join and is NULL when it missed. The
-- pair tells you which happened.
--
-- The grain depends on stg_users.user_id being unique. That is enforced by a
-- dbt test on stg_users, not assumed here — a duplicate would fan this join
-- out silently rather than fail.

with posts as (
    select * from {{ ref('stg_posts') }}
),

users as (
    select * from {{ ref('stg_users') }}
),

final as (
    select
        -- Post fields — the fact side
        p.post_id,
        p.post_type,
        p.parent_id,
        p.title,
        p.tags_array,
        p.score,
        p.view_count,
        p.answer_count,
        p.comment_count,
        p.creation_date          as post_creation_date,

        -- The author id as recorded on the post. Kept whether or not the join
        -- found a matching user; see the header.
        p.owner_user_id,

        -- User fields — the dimension side. All NULL when the join misses.
        u.user_id,
        u.display_name,
        u.reputation,
        u.up_votes,
        u.down_votes,
        u.profile_views          as user_profile_views,
        u.location               as user_location,
        u.website_url            as user_website_url,
        u.creation_date          as user_creation_date,
        u.last_access_date       as user_last_access_date,

        -- Explicit flag rather than making every consumer re-derive
        -- `user_id is null`, and it distinguishes the two ways a post can have
        -- no author: never had one, or had one we could not resolve.
        case
            when p.owner_user_id is null then 'anonymous'
            when u.user_id is null       then 'unresolved'
            else 'resolved'
        end as author_status

    from posts p
    left join users u on p.owner_user_id = u.user_id
)

select * from final
