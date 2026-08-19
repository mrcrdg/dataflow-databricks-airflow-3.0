-- Silver: cleaned, typed users.
--
-- Mirrors stg_posts: rename Id -> user_id, everything to snake_case, explicit
-- column list rather than select *. No filtering — Id = -1 is the Community
-- pseudo-user and it genuinely owns posts (community-wiki content), so dropping
-- "invalid-looking" ids would lose those rows from the join downstream.
--
-- about_me is deliberately excluded: it is an HTML blob, it is the largest
-- column in the table, and nothing downstream reads it. It stays available in
-- bronze if that ever changes.

with users as (
    select * from {{ source('bronze', 'users') }}
),

final as (
    select
        u.Id              as user_id,
        u.AccountId       as account_id,
        u.DisplayName     as display_name,

        u.Reputation      as reputation,
        u.UpVotes         as up_votes,
        u.DownVotes       as down_votes,
        u.Views           as profile_views,

        -- Present-but-empty and absent are different in the source, and both
        -- occur. nullif collapses them here, in silver, where that decision
        -- belongs — bronze keeps them apart.
        nullif(u.Location, '')    as location,
        nullif(u.WebsiteUrl, '')  as website_url,

        u.CreationDate    as creation_date,
        u.LastAccessDate  as last_access_date

    from users u
)

select * from final
