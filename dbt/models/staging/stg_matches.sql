select
    m.match_id,
    to_timestamp((m.payload->>'start_time')::bigint) as started_at,
    (m.payload->>'duration')::integer as duration_seconds,
    (m.payload->>'radiant_win')::boolean as radiant_win,
    nullif((coalesce(m.payload->>'leagueid', p.payload->>'leagueid'))::bigint, 0) as league_id,
    coalesce(p.payload->>'league_name', 'Unknown tournament') as league_name,
    nullif(coalesce((m.payload->>'radiant_team_id')::bigint,
                   (p.payload->>'radiant_team_id')::bigint), 0) as radiant_team_id,
    coalesce(m.payload->'radiant_team'->>'name', p.payload->>'radiant_name', 'Unknown')
        as radiant_name,
    nullif(coalesce((m.payload->>'dire_team_id')::bigint,
                   (p.payload->>'dire_team_id')::bigint), 0) as dire_team_id,
    coalesce(m.payload->'dire_team'->>'name', p.payload->>'dire_name', 'Unknown') as dire_name,
    (m.payload->>'patch')::integer as patch_id,
    jsonb_array_length(coalesce(nullif(m.payload->'picks_bans', 'null'::jsonb), '[]'::jsonb)) > 0
        as has_draft,
    m.fetched_at
from {{ source('raw', 'match_payloads') }} m
join {{ source('raw', 'pro_matches') }} p using (match_id)
where (m.payload->>'radiant_win') is not null
