select team_id, roster_spell, roster_id, player_ids,
       min(started_at) as first_seen_at,
       max(started_at) as last_seen_at,
       count(*) as games, sum(won::integer) as wins,
       round(100.0*avg(won::integer),2) as win_rate
from {{ ref('fct_team_rosters') }}
group by team_id, roster_spell, roster_id, player_ids
