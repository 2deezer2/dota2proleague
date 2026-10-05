select match_id, draft_order from {{ ref('stg_draft') }}
group by match_id, draft_order having count(*) > 1
