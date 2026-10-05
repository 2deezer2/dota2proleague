with observed as (
    select distinct on (team_id) team_id, team_name
    from {{ ref('fct_team_matches') }} order by team_id,started_at desc,match_id desc
)
select o.team_id, coalesce(p.payload->>'name',o.team_name) as name,
       p.payload->>'tag' as tag, p.fetched_at as profile_fetched_at
from observed o left join {{ source('raw','team_profiles') }} p using (team_id)
