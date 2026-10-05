select
    m.match_id,
    (action->>'order')::integer as draft_order,
    (action->>'hero_id')::integer as hero_id,
    coalesce(h.name, 'Hero ' || (action->>'hero_id')) as hero_name,
    (action->>'is_pick')::boolean as is_pick,
    (action->>'team')::integer as side
from {{ source('raw', 'match_payloads') }} m
cross join lateral jsonb_array_elements(
    coalesce(nullif(m.payload->'picks_bans', 'null'::jsonb), '[]'::jsonb)
) action
left join {{ source('raw', 'heroes') }} h on h.hero_id = (action->>'hero_id')::integer
