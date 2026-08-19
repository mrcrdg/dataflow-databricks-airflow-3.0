-- The notebook's validate_stg_posts checked that no post has an empty tag list.
-- Ported faithfully but corrected: a NULL array (an answer, which has no tags)
-- is fine; only a non-null *empty* array would signal a normalization bug.
-- Ported naively as "tags_array must be non-empty", this would fail on every
-- answer row. This is the fixed form.
select post_id
from {{ ref('stg_posts') }}
where tags_array is not null
  and len(tags_array) = 0
